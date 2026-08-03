from __future__ import annotations

import email
import base64
import json
import re
import zlib
from email import policy
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.prompts.document_selection_prompt import build_document_selection_messages
from app.services.document_metadata_service import DocumentMetadataService
from app.services.document_metadata_service import build_citation_record, build_source_uri
from app.services.document_intelligence_service import DocumentIntelligenceService
from app.services.semantic_retrieval_service import SemanticRetrievalService
from app.services.tabular_text_service import TabularTextService
from app.services.uploaded_document_search_service import UploadedDocumentSearchService


LOOKUP_KEYS = (
    "vendor_id",
    "employee_id",
    "transaction_id",
    "contract_id",
    "investigation_id",
)


class DocumentRetrievalAgent:
    def __init__(self, db: Session) -> None:
        self.service = DocumentMetadataService(db)
        self.intelligence_service = DocumentIntelligenceService()
        self.semantic_service = SemanticRetrievalService(db)
        self.uploaded_search_service = UploadedDocumentSearchService(db)
        self.tabular_text_service = TabularTextService()
        self.settings = get_settings()

    def retrieve(
        self,
        *,
        query: str,
        structured_intent: dict[str, Any],
        transaction_results: list[dict[str, Any]],
        attached_document_ids: list[str] | None = None,
        trace_context: Any | None = None,
    ) -> dict[str, Any]:
        retrieval_span = trace_context.begin_span(
            "document_retrieval_agent",
            input_payload={
                "query": query,
                "structured_intent": structured_intent,
                "transaction_count": len(transaction_results),
            },
            metadata={"service": "DocumentRetrievalAgent"},
        ) if trace_context else None

        lookup_values = self._collect_lookup_values(structured_intent, transaction_results)
        documents: dict[str, dict[str, Any]] = {}

        for vendor_id in lookup_values["vendor_id"]:
            for document in self.service.get_documents_by_vendor_id(vendor_id):
                documents[document["document_id"]] = document

        for employee_id in lookup_values["employee_id"]:
            for document in self.service.get_documents_by_employee_id(employee_id):
                documents[document["document_id"]] = document

        for transaction_id in lookup_values["transaction_id"]:
            for document in self.service.get_documents_by_transaction_id(transaction_id):
                documents[document["document_id"]] = document

        for contract_id in lookup_values["contract_id"]:
            for document in self.service.get_documents_by_contract_id(contract_id):
                documents[document["document_id"]] = document

        for investigation_id in lookup_values["investigation_id"]:
            for document in self.service.get_documents_by_investigation_id(investigation_id):
                documents[document["document_id"]] = document

        for document_id in attached_document_ids or []:
            document = self.service.get_document_by_id(document_id)
            if document:
                documents[document["document_id"]] = document

        document_list = self._enrich_documents(list(documents.values()), transaction_results)
        document_list = [self._attach_content_snippet(document) for document in document_list]
        document_list = [self._attach_intelligence(document) for document in document_list]
        document_list = [self._attach_citation_metadata(document) for document in document_list]
        document_list = self._attach_selection_explanations(
            query=query,
            structured_intent=structured_intent,
            transaction_results=transaction_results,
            documents=document_list,
            trace_context=trace_context,
        )

        semantic_documents: list[dict[str, Any]] = []
        semantic_sources: list[str] = []
        if self._should_run_semantic_search(query, document_list):
            semantic_result = self.semantic_service.search(
                query=query,
                top_k=5,
                exclude_document_ids={str(document.get("document_id")) for document in document_list if document.get("document_id")},
            )
            semantic_documents = list(semantic_result.get("semantic_evidence", []))
            semantic_sources = list(semantic_result.get("sources", []))

        uploaded_documents: list[dict[str, Any]] = []
        if attached_document_ids or self._should_run_semantic_search(query, document_list) or not document_list:
            uploaded_documents = self.uploaded_search_service.search(
                query=query,
                top_k=5,
                attached_document_ids={str(document_id) for document_id in (attached_document_ids or []) if document_id},
                exclude_document_ids={str(document.get("document_id")) for document in document_list if document.get("document_id")},
            )

        document_list = document_list + uploaded_documents
        document_list = document_list + semantic_documents
        sources = self._build_sources(document_list)
        for source in semantic_sources:
            if source not in sources:
                sources.append(source)
        if uploaded_documents and "uploaded_document_search" not in sources:
            sources.append("uploaded_document_search")
        document_intelligence = self.intelligence_service.summarize_documents(document_list)
        if retrieval_span:
            retrieval_span.finish(
                output={
                    "document_count": len(document_list),
                    "sources": sources,
                    "uploaded_document_count": len(uploaded_documents),
                    "semantic_evidence_count": len(semantic_documents),
                },
                metadata={
                    "document_count": len(document_list),
                    "uploaded_document_count": len(uploaded_documents),
                    "semantic_evidence_count": len(semantic_documents),
                    "sources": sources,
                },
            )

        return {
            "agent": "document_retrieval_agent",
            "query": query,
            "lookup_values": lookup_values,
            "documents": document_list,
            "document_count": len(document_list),
            "sources": sources,
            "document_intelligence": document_intelligence,
            "uploaded_document_evidence": uploaded_documents,
            "semantic_evidence": semantic_documents,
        }

    def _attach_selection_explanations(
        self,
        *,
        query: str,
        structured_intent: dict[str, Any],
        transaction_results: list[dict[str, Any]],
        documents: list[dict[str, Any]],
        trace_context: Any | None = None,
    ) -> list[dict[str, Any]]:
        if not documents:
            return []

        explanations = self._generate_selection_explanations(
            query=query,
            structured_intent=structured_intent,
            transaction_results=transaction_results,
            documents=documents,
            trace_context=trace_context,
        )
        explanation_by_id = {
            str(item.get("document_id")): item
            for item in explanations
            if isinstance(item, dict) and item.get("document_id") not in (None, "")
        }

        enriched_documents: list[dict[str, Any]] = []
        for document in documents:
            document_id = str(document.get("document_id") or "")
            explanation = explanation_by_id.get(document_id)
            if not explanation:
                explanation = self._deterministic_selection_explanation(
                    query=query,
                    structured_intent=structured_intent,
                    transaction_results=transaction_results,
                    document=document,
                )
            enriched_documents.append(
                {
                    **document,
                    "selection_explanation": explanation,
                    "selection_reason": explanation.get("selection_reason", ""),
                    "supports": explanation.get("supports", ""),
                    "relevance_summary": explanation.get("relevance_summary", ""),
                    "confidence_note": explanation.get("confidence_note", ""),
                }
            )
        return enriched_documents

    def _generate_selection_explanations(
        self,
        *,
        query: str,
        structured_intent: dict[str, Any],
        transaction_results: list[dict[str, Any]],
        documents: list[dict[str, Any]],
        trace_context: Any | None = None,
    ) -> list[dict[str, Any]]:
        if not self.settings.openai_api_key:
            return [
                self._deterministic_selection_explanation(
                    query=query,
                    structured_intent=structured_intent,
                    transaction_results=transaction_results,
                    document=document,
                )
                for document in documents
            ]

        try:
            from openai import OpenAI
        except ImportError:
            return [
                self._deterministic_selection_explanation(
                    query=query,
                    structured_intent=structured_intent,
                    transaction_results=transaction_results,
                    document=document,
                )
                for document in documents
            ]

        payload_documents = [self._build_document_selection_payload(document) for document in documents]
        payload_evidence = [self._build_structured_evidence_payload(row) for row in transaction_results]

        try:
            client = OpenAI(api_key=self.settings.openai_api_key)
            llm_span = trace_context.begin_span(
                "document_selection_llm",
                input_payload={
                    "query": query,
                    "intent": structured_intent,
                    "structured_evidence": payload_evidence,
                    "documents": payload_documents,
                },
                metadata={"service": "DocumentRetrievalAgent", "model": self.settings.openai_model},
            ) if trace_context else None
            response = client.chat.completions.create(
                model=self.settings.openai_model,
                temperature=0,
                messages=build_document_selection_messages(
                    query=query,
                    intent=structured_intent,
                    structured_evidence=payload_evidence,
                    documents=payload_documents,
                ),
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("LLM returned an empty document selection explanation.")
            usage = getattr(response, "usage", None)
            usage_payload = {}
            if usage is not None:
                usage_payload = {
                    "prompt_tokens": getattr(usage, "prompt_tokens", None),
                    "completion_tokens": getattr(usage, "completion_tokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None),
                }
            if llm_span:
                llm_span.finish(
                    output=content,
                    metadata={"service": "DocumentRetrievalAgent", "usage": usage_payload, "model": self.settings.openai_model},
                )
            parsed = self._parse_selection_explanations(content)
            if parsed:
                return parsed
        except Exception:
            pass

        return [
            self._deterministic_selection_explanation(
                query=query,
            structured_intent=structured_intent,
            transaction_results=transaction_results,
            document=document,
        )
            for document in documents
        ]

    def _parse_selection_explanations(self, response_text: str) -> list[dict[str, Any]]:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            return []
        documents = payload.get("documents")
        if not isinstance(documents, list):
            return []

        parsed: list[dict[str, Any]] = []
        for item in documents:
            if not isinstance(item, dict):
                continue
            document_id = str(item.get("document_id") or "").strip()
            if not document_id:
                continue
            parsed.append(
                {
                    "document_id": document_id,
                    "selection_reason": str(item.get("selection_reason") or "").strip(),
                    "supports": str(item.get("supports") or "").strip(),
                    "relevance_summary": str(item.get("relevance_summary") or "").strip(),
                    "confidence_note": str(item.get("confidence_note") or "").strip(),
                }
            )
        return parsed

    def _deterministic_selection_explanation(
        self,
        *,
        query: str,
        structured_intent: dict[str, Any],
        transaction_results: list[dict[str, Any]],
        document: dict[str, Any],
    ) -> dict[str, Any]:
        document_id = str(document.get("document_id") or "")
        reason_selected = str(document.get("reason_selected") or "Document was selected from the retrieved evidence.").strip()
        document_category = str(document.get("document_category") or document.get("document_type") or "document").strip()
        query_focus = self._query_focus_label(query, structured_intent)
        linked_transaction = document.get("linked_transaction")
        relevance_bits = [f"selected for {query_focus}"]
        if linked_transaction:
            relevance_bits.append(f"linked to transaction {linked_transaction}")
        if transaction_results:
            relevance_bits.append(f"derived from {len(transaction_results)} structured record(s)")
        relevance_bits.append(f"document category {document_category}")

        support_bits = [reason_selected]
        citation_text = str(document.get("citation_text") or document.get("content_snippet") or "").strip()
        if citation_text:
            support_bits.append("citation text supports the retrieved audit evidence")
        if document.get("document_signals"):
            support_bits.append("document signals reinforce the audit context")

        confidence_note = "Grounded in retrieved document metadata and cited evidence."
        if not citation_text:
            confidence_note = "Grounded in metadata linkage; no citation text was available."

        return {
            "document_id": document_id,
            "selection_reason": reason_selected,
            "supports": "; ".join(dict.fromkeys(support_bits)),
            "relevance_summary": "; ".join(dict.fromkeys(relevance_bits)),
            "confidence_note": confidence_note,
        }

    def _query_focus_label(self, query: str, structured_intent: dict[str, Any]) -> str:
        intent = str(structured_intent.get("intent") or "").strip()
        if intent:
            return intent.replace("_", " ")
        compact_query = re.sub(r"\s+", " ", query).strip()
        return compact_query[:60] if compact_query else "the audit question"

    def _build_document_selection_payload(self, document: dict[str, Any]) -> dict[str, Any]:
        return {
            "document_id": document.get("document_id"),
            "document_type": document.get("document_type"),
            "document_category": document.get("document_category"),
            "file_name": document.get("file_name"),
            "source_uri": document.get("source_uri"),
            "page_number": document.get("page_number"),
            "section_title": document.get("section_title"),
            "citation_text": document.get("citation_text") or document.get("content_snippet") or "",
            "linked_transaction": document.get("linked_transaction"),
            "reason_selected": document.get("reason_selected"),
            "relevance_score": document.get("relevance_score"),
        }

    def _build_structured_evidence_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "transaction_id": row.get("transaction_id"),
            "vendor_id": row.get("vendor_id"),
            "contract_id": row.get("contract_id"),
            "approval_id": row.get("approval_id"),
            "finding_id": row.get("finding_id"),
            "status": row.get("status"),
            "risk_score": row.get("risk_score"),
            "amount": row.get("amount"),
            "currency": row.get("currency"),
        }

    def _collect_lookup_values(
        self,
        structured_intent: dict[str, Any],
        transaction_results: list[dict[str, Any]],
    ) -> dict[str, list[str]]:
        lookup_values: dict[str, set[str]] = {key: set() for key in LOOKUP_KEYS}

        filters = structured_intent.get("filters") if isinstance(structured_intent.get("filters"), dict) else {}
        for key in LOOKUP_KEYS:
            value = filters.get(key)
            if isinstance(value, dict):
                value = value.get("value")
            if value not in (None, ""):
                lookup_values[key].add(str(value))

        for row in transaction_results:
            vendor_id = row.get("vendor_id")
            transaction_id = row.get("transaction_id")
            employee_id = row.get("employee_id")
            contract_id = row.get("contract_id")
            investigation_id = row.get("investigation_id")

            for key, value in (
                ("vendor_id", vendor_id),
                ("transaction_id", transaction_id),
                ("employee_id", employee_id),
                ("contract_id", contract_id),
                ("investigation_id", investigation_id),
            ):
                if value not in (None, ""):
                    lookup_values[key].add(str(value))

        return {key: sorted(values) for key, values in lookup_values.items()}

    def _enrich_documents(
        self,
        documents: list[dict[str, Any]],
        transaction_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        transaction_ids = [str(row.get("transaction_id")) for row in transaction_results if row.get("transaction_id")]
        enriched: list[dict[str, Any]] = []

        for document in documents:
            linked_transaction = document.get("related_transaction_id") or (transaction_ids[0] if transaction_ids else None)
            reason_selected = self._reason_selected(document, linked_transaction)
            enriched.append(
                {
                    **document,
                    "linked_transaction": linked_transaction,
                    "reason_selected": reason_selected,
                    "retrieval_mode": "metadata",
                }
            )
        return enriched

    def _should_run_semantic_search(self, query: str, exact_documents: list[dict[str, Any]]) -> bool:
        lowered = query.lower()
        if not exact_documents:
            return True

        semantic_signals = (
            "policy",
            "policies",
            "violat",
            "evidence",
            "clause",
            "section",
            "support",
            "similar",
            "related",
            "why",
            "how",
            "compliance",
            "control",
            "threshold",
            "limit",
            "spreadsheet",
            "sheet",
            "workbook",
            "row",
            "column",
            "excel",
            "csv",
        )
        return any(signal in lowered for signal in semantic_signals)

    def _reason_selected(self, document: dict[str, Any], linked_transaction: str | None) -> str:
        file_name = str(document.get("file_name") or "").lower()
        if file_name.endswith((".xlsx", ".xlsm", ".xltx", ".xltm", ".csv")):
            return "Spreadsheet evidence was selected because it matched the retrieved audit context."
        if document.get("related_transaction_id"):
            return "Document references a transaction returned by the Transaction Agent."
        if document.get("related_vendor_id"):
            return "Document references a vendor returned by the Transaction Agent."
        if document.get("related_employee_id"):
            return "Document references an employee linked to the transaction evidence."
        if document.get("related_contract_id"):
            return "Document references a contract linked to the retrieved evidence."
        if document.get("related_investigation_id"):
            return "Document references an investigation linked to the retrieved evidence."
        if linked_transaction:
            return "Document was selected because the Transaction Agent returned a related transaction context."
        return "Document was selected from metadata linkage."

    def _attach_content_snippet(self, document: dict[str, Any]) -> dict[str, Any]:
        file_path = document.get("file_path")
        content_snippet = self._extract_content_snippet(str(file_path)) if file_path else ""
        return {
            **document,
            "content_snippet": content_snippet,
        }

    def _attach_intelligence(self, document: dict[str, Any]) -> dict[str, Any]:
        intelligence = self.intelligence_service.classify(document)
        return {
            **document,
            "document_intelligence": intelligence,
            "document_type": intelligence["document_type"],
            "document_signals": intelligence["signals"],
            "document_risk_contribution": intelligence["risk_contribution"],
        }

    def _attach_citation_metadata(self, document: dict[str, Any]) -> dict[str, Any]:
        citation = build_citation_record(
            document,
            page_number=document.get("page_number"),
            section_title=document.get("section_title"),
            citation_text=document.get("citation_text") or document.get("content_snippet"),
            anchor_text=document.get("anchor_text") or document.get("citation_text") or document.get("content_snippet"),
            start_offset=document.get("start_offset"),
            end_offset=document.get("end_offset"),
            chunk_id=document.get("chunk_id"),
            relevance_score=document.get("relevance_score"),
        )
        return {
            **document,
            **citation,
            "source_uri": document.get("source_uri") or build_source_uri(document),
        }

    def _extract_content_snippet(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return ""

        suffix = path.suffix.lower()
        try:
            if suffix in {".txt", ".md", ".log"}:
                content = path.read_text(encoding="utf-8", errors="ignore")
            elif suffix == ".csv":
                content = self.tabular_text_service.extract_text(path)
            elif suffix in self.tabular_text_service.SPREADSHEET_SUFFIXES:
                content = self.tabular_text_service.extract_text(path)
            elif suffix == ".eml":
                content = self._read_eml(path)
            elif suffix == ".docx":
                content = self._read_docx(path)
            elif suffix == ".pdf":
                content = self._read_pdf(path)
            else:
                return ""
        except Exception:
            return ""

        return self._first_meaningful_snippet(content)

    def _read_eml(self, path: Path) -> str:
        with path.open("rb") as handle:
            message = email.message_from_binary_file(handle, policy=policy.default)

        fragments: list[str] = []
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_content()
                    if isinstance(payload, str):
                        fragments.append(payload)
        else:
            payload = message.get_content()
            if isinstance(payload, str):
                fragments.append(payload)
        return "\n".join(fragments)

    def _read_docx(self, path: Path) -> str:
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        with ZipFile(path) as archive:
            with archive.open("word/document.xml") as document_xml:
                tree = ET.parse(document_xml)
        paragraphs: list[str] = []
        for paragraph in tree.findall(".//w:p", namespace):
            texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
            text = "".join(texts).strip()
            if text:
                paragraphs.append(text)
        return "\n".join(paragraphs)

    def _read_pdf(self, path: Path) -> str:
        raw_text = self._extract_pdf_raw_text(path)
        if raw_text:
            return raw_text
        return ""

    def _first_meaningful_snippet(self, content: str) -> str:
        normalized = re.sub(r"\s+", " ", content).strip()
        if not normalized:
            return ""
        snippet = normalized[:240]
        if len(normalized) > 240 and " " in snippet:
            snippet = snippet.rsplit(" ", 1)[0].strip()
        return f"{snippet}..." if len(normalized) > len(snippet) else snippet

    def _first_meaningful_paragraph(self, content: str) -> str:
        normalized = re.sub(r"\r", "\n", content)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]

        for block in blocks:
            compact = re.sub(r"\s+", " ", block).strip()
            if len(compact) >= 40:
                return compact

        compact = re.sub(r"\s+", " ", normalized).strip()
        return compact if len(compact) >= 40 else compact

    def _extract_pdf_raw_text(self, path: Path) -> str:
        try:
            data = path.read_bytes()
        except Exception:
            return ""

        offset = 0
        while True:
            stream_start = data.find(b"stream", offset)
            if stream_start == -1:
                break

            content_start = data.find(b"\n", stream_start)
            if content_start == -1:
                break
            content_start += 1
            if content_start > 0 and data[content_start - 2 : content_start] == b"\r\n":
                content_start += 0

            endstream = data.find(b"endstream", content_start)
            if endstream == -1:
                break

            chunk = data[content_start:endstream].strip(b"\r\n")
            decoded = self._decode_pdf_stream(chunk)
            if decoded:
                text = self._extract_text_from_pdf_stream(decoded)
                if text:
                    paragraph = self._first_meaningful_paragraph(text)
                    if paragraph:
                        return paragraph

            offset = endstream + len(b"endstream")

        fallback_text = self._extract_text_from_pdf_bytes(data)
        if fallback_text:
            paragraph = self._first_meaningful_paragraph(fallback_text)
            if paragraph:
                return paragraph
        return ""

    def _decode_pdf_stream(self, chunk: bytes) -> bytes:
        candidates = [chunk, chunk.strip(b"\r\n")]
        for candidate in candidates:
            try:
                return zlib.decompress(candidate)
            except Exception:
                pass
            try:
                ascii85_decoded = base64.a85decode(candidate, adobe=True)
                return zlib.decompress(ascii85_decoded)
            except Exception:
                pass
        return chunk

    def _extract_text_from_pdf_stream(self, stream_data: bytes) -> str:
        try:
            text = stream_data.decode("latin-1", errors="ignore")
        except Exception:
            return ""

        fragments: list[str] = []
        fragments.extend(self._extract_pdf_literal_strings(text))
        fragments.extend(self._extract_pdf_hex_strings(text))
        if fragments:
            return "\n".join(fragments)
        return self._extract_text_from_pdf_bytes(stream_data)

    def _extract_text_from_pdf_bytes(self, data: bytes) -> str:
        try:
            text = data.decode("latin-1", errors="ignore")
        except Exception:
            return ""

        fragments: list[str] = []
        fragments.extend(self._extract_pdf_literal_strings(text))
        fragments.extend(self._extract_pdf_hex_strings(text))
        return "\n".join(fragments)

    def _extract_pdf_literal_strings(self, text: str) -> list[str]:
        strings = re.findall(r"\((.*?)\)\s*T[Jj]", text, flags=re.DOTALL)
        cleaned: list[str] = []
        for value in strings:
            candidate = re.sub(r"\\([nrtbf()\\])", " ", value)
            candidate = re.sub(r"\\[0-7]{1,3}", " ", candidate)
            candidate = re.sub(r"\s+", " ", candidate).strip()
            if candidate:
                cleaned.append(candidate)

        array_strings = re.findall(r"\[(.*?)\]\s*TJ", text, flags=re.DOTALL)
        for array in array_strings:
            cleaned.extend(self._extract_pdf_literal_strings(array))
            cleaned.extend(self._extract_pdf_hex_strings(array))
        return cleaned

    def _extract_pdf_hex_strings(self, text: str) -> list[str]:
        hex_values = re.findall(r"<([0-9A-Fa-f\s]+)>\s*T[Jj]", text, flags=re.DOTALL)
        cleaned: list[str] = []
        for value in hex_values:
            compact = re.sub(r"\s+", "", value)
            if not compact:
                continue
            try:
                if len(compact) % 2 == 1:
                    compact = compact[:-1]
                decoded = bytes.fromhex(compact).decode("utf-16-be", errors="ignore").strip()
                if not decoded:
                    decoded = bytes.fromhex(compact).decode("latin-1", errors="ignore").strip()
            except Exception:
                decoded = ""
            if decoded:
                cleaned.append(decoded)
        return cleaned

    def _build_sources(self, documents: Iterable[dict[str, Any]]) -> list[str]:
        sources: list[str] = []
        for document in documents:
            file_path = document.get("file_path")
            source_metadata_file = document.get("source_metadata_file")
            if file_path and file_path not in sources:
                sources.append(file_path)
            if source_metadata_file and source_metadata_file not in sources:
                sources.append(source_metadata_file)
        return sources
