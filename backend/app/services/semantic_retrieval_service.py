from __future__ import annotations

import base64
import email
import json
import re
import sys
import zlib
from email import policy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import get_settings
from app.models import DocumentMetadata
from app.services.document_metadata_service import build_citation_record, build_source_uri
from app.services.document_intelligence_service import DocumentIntelligenceService
from app.services.tabular_text_service import TabularTextService
from rag.ingestion.document_chunker import DocumentChunker
from rag.vector_store.vector_store_service import VectorStoreService


class SemanticRetrievalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.documents_dir = Path(self.settings.rag_documents_dir)
        self.chunker = DocumentChunker()
        self.vector_store = VectorStoreService()
        self.intelligence_service = DocumentIntelligenceService()
        self.tabular_text_service = TabularTextService()

    def search(
        self,
        *,
        query: str,
        top_k: int = 5,
        exclude_document_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        exclude_document_ids = exclude_document_ids or set()
        documents = self._load_documents(exclude_document_ids=exclude_document_ids)
        chunks: list[dict[str, Any]] = []

        for document in documents:
            cached_chunks = self._load_cached_chunks(document)
            if cached_chunks:
                chunks.extend(cached_chunks)
                continue

            chunks.extend(self.build_document_index(document))

        ranked_chunks = self.vector_store.search(query, chunks, top_k=top_k)
        semantic_evidence = [self._build_evidence_item(chunk, query=query) for chunk in ranked_chunks]
        source_labels = ["semantic_retrieval"]
        if any(str(chunk.get("source_type") or "").lower() in {"spreadsheet", "tabular"} for chunk in ranked_chunks):
            source_labels.append("tabular_semantic_retrieval")

        return {
            "semantic_evidence": semantic_evidence,
            "documents_scanned": len(documents),
            "chunks_considered": len(chunks),
            "sources": source_labels,
        }

    def build_document_index(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        """Build page-aware chunks plus embeddings for a single document."""
        units = self._extract_document_units(document)
        chunks: list[dict[str, Any]] = []
        for unit in units:
            content = unit.get("content") or ""
            if not content.strip():
                continue
            chunks.extend(self.chunker.chunk_document(document=unit, content=content))

        if not chunks:
            return []

        contents = [str(chunk.get("content") or "") for chunk in chunks]
        vectors = self.vector_store.embedding_service.embed_many(contents)
        for chunk, vector in zip(chunks, vectors):
            chunk["embedding"] = vector
        return chunks

    def _load_documents(self, *, exclude_document_ids: set[str]) -> list[dict[str, Any]]:
        stmt = select(DocumentMetadata).order_by(DocumentMetadata.document_id)
        rows = self.db.scalars(stmt).all()
        documents: list[dict[str, Any]] = []
        for row in rows:
            if row.document_id in exclude_document_ids:
                continue

            file_path = Path(row.file_path) if row.file_path else self._resolve_document_path(row)
            if not file_path.exists() or not file_path.is_file():
                continue

            documents.append(
                {
                    "document_id": row.document_id,
                    "document_type": row.document_type,
                    "document_category": row.document_category,
                    "related_vendor_id": row.related_vendor_id,
                    "related_employee_id": row.related_employee_id,
                    "related_transaction_id": row.related_transaction_id,
                    "related_contract_id": row.related_contract_id,
                    "related_investigation_id": row.related_investigation_id,
                    "creation_date": row.creation_date.isoformat() if row.creation_date else None,
                    "file_name": row.file_name,
                    "file_path": str(file_path),
                    "source_metadata_file": row.source_metadata_file,
                }
            )
        return documents

    def _load_cached_chunks(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        file_path = document.get("file_path")
        if not file_path:
            return []
        artifact_path = Path(str(file_path)).with_suffix(f"{Path(str(file_path)).suffix}.meta.json")
        if not artifact_path.exists() or not artifact_path.is_file():
            return []

        try:
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        except Exception:
            return []

        chunks = artifact.get("chunks")
        if not isinstance(chunks, list):
            return []

        cached: list[dict[str, Any]] = []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            content = str(chunk.get("content") or "").strip()
            if not content:
                continue
            cached.append(
                {
                    **document,
                    **chunk,
                    "source_uri": build_source_uri(document),
                    "content": content,
                    "embedding": chunk.get("embedding"),
                }
            )
        return cached

    def _resolve_document_path(self, row: DocumentMetadata) -> Path:
        if row.file_path:
            return Path(row.file_path)
        return self.documents_dir / row.file_name

    def _extract_document_units(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        path = Path(document["file_path"])
        suffix = path.suffix.lower()

        if suffix in self.tabular_text_service.SPREADSHEET_SUFFIXES:
            tabular_units = self.tabular_text_service.extract_units(path)
            if tabular_units:
                return [
                    {
                        **document,
                        **unit,
                        "source_uri": build_source_uri(document),
                        "content": unit.get("content") or "",
                    }
                    for unit in tabular_units
                    if str(unit.get("content") or "").strip()
                ]

        if suffix == ".csv":
            tabular_units = self.tabular_text_service.extract_units(path)
            if tabular_units:
                return [
                    {
                        **document,
                        **unit,
                        "source_uri": build_source_uri(document),
                        "content": unit.get("content") or "",
                    }
                    for unit in tabular_units
                    if str(unit.get("content") or "").strip()
                ]

        if suffix == ".pdf":
            pdf_units = self._extract_pdf_units(document, path)
            if pdf_units:
                return pdf_units

        content = self._read_document_content(path)
        if not content:
            return []

        return [
            {
                **document,
                "page_number": 1,
                "section_title": self._infer_section_title(content),
                "citation_text": self._build_snippet(content),
                "source_uri": build_source_uri(document),
                "content": content,
            }
        ]

    def _extract_pdf_units(self, document: dict[str, Any], path: Path) -> list[dict[str, Any]]:
        reader = self._load_pdf_reader(path)
        if reader is None:
            content = self._read_pdf(path)
            if not content:
                return []
            return [
                {
                    **document,
                    "page_number": 1,
                    "section_title": self._infer_section_title(content),
                    "citation_text": self._build_snippet(content),
                    "source_uri": build_source_uri(document),
                    "content": content,
                }
            ]

        units: list[dict[str, Any]] = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if not text.strip():
                continue
            units.append(
                {
                    **document,
                    "page_number": page_number,
                    "section_title": self._infer_section_title(text),
                    "citation_text": self._build_snippet(text),
                    "source_uri": build_source_uri(document),
                    "content": text,
                }
            )

        if units:
            return units

        content = self._read_pdf(path)
        if not content:
            return []
        return [
            {
                **document,
                "page_number": 1,
                "section_title": self._infer_section_title(content),
                "citation_text": self._build_snippet(content),
                "source_uri": build_source_uri(document),
                "content": content,
            }
        ]

    def _load_pdf_reader(self, path: Path) -> Any | None:
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception:
            try:
                from PyPDF2 import PdfReader  # type: ignore
            except Exception:
                return None

        try:
            return PdfReader(str(path))
        except Exception:
            return None

    def _build_evidence_item(self, chunk: dict[str, Any], *, query: str) -> dict[str, Any]:
        document = {
            "document_id": chunk.get("document_id"),
            "document_type": chunk.get("document_type"),
            "document_category": chunk.get("document_category"),
            "related_vendor_id": chunk.get("related_vendor_id"),
            "related_employee_id": chunk.get("related_employee_id"),
            "related_transaction_id": chunk.get("related_transaction_id"),
            "related_contract_id": chunk.get("related_contract_id"),
            "related_investigation_id": chunk.get("related_investigation_id"),
            "creation_date": chunk.get("creation_date"),
            "file_name": chunk.get("file_name"),
            "file_path": chunk.get("file_path"),
            "source_metadata_file": chunk.get("source_metadata_file"),
        }
        intelligence = self.intelligence_service.classify(document)
        content = chunk.get("content") or ""
        snippet = chunk.get("content_snippet") or self._build_snippet(content)
        citation = build_citation_record(
            {**document, **chunk},
            page_number=chunk.get("page_number"),
            section_title=chunk.get("section_title"),
            citation_text=chunk.get("citation_text") or snippet,
            anchor_text=chunk.get("anchor_text") or chunk.get("citation_text") or snippet,
            start_offset=chunk.get("start_offset"),
            end_offset=chunk.get("end_offset"),
            chunk_id=chunk.get("chunk_id"),
            relevance_score=chunk.get("relevance_score", 0.0),
        )

        return {
            **citation,
            **document,
            "source_uri": build_source_uri({**document, **chunk}),
            "chunk_index": chunk.get("chunk_index"),
            "anchor_text": chunk.get("anchor_text") or chunk.get("citation_text") or snippet,
            "start_offset": chunk.get("start_offset"),
            "end_offset": chunk.get("end_offset"),
            "content_hash": chunk.get("content_hash"),
            "relevance_score": chunk.get("relevance_score", 0.0),
            "content": content,
            "content_snippet": snippet,
            "retrieval_mode": "semantic",
            "linked_transaction": chunk.get("related_transaction_id"),
            "reason_selected": self._reason_selected(query=query, document=document, page_number=chunk.get("page_number")),
            "document_intelligence": intelligence,
            "document_signals": intelligence["signals"],
            "document_risk_contribution": intelligence["risk_contribution"],
        }

    def _reason_selected(self, *, query: str, document: dict[str, Any], page_number: int | None = None) -> str:
        lowered_query = query.lower()
        document_type = str(document.get("document_type") or "").upper()
        document_category = str(document.get("document_category") or "").lower()
        file_name = str(document.get("file_name") or "").lower()
        page_text = f" page {page_number}" if page_number is not None else ""

        if file_name.endswith((".xlsx", ".xlsm", ".xltx", ".xltm", ".csv")) or document_type == "SPREADSHEET":
            return f"Spreadsheet or tabular evidence matched the investigation question{page_text}."
        if "policy" in lowered_query or "violat" in lowered_query or "clause" in lowered_query:
            if "policy" in document_type.lower() or document_category == "policies":
                return f"Relevant policy clause matched the investigation question{page_text}."
            if document_type in {"SOP", "AUDIT_REPORT"}:
                return f"Relevant control document matched the policy reasoning query{page_text}."
        if "evidence" in lowered_query or "support" in lowered_query or "why" in lowered_query:
            return f"Relevant document chunk provides supporting evidence for the query{page_text}."
        if "similar" in lowered_query or "related" in lowered_query:
            return f"Document chunk semantically matches the requested context{page_text}."
        return f"Document chunk semantically matches the investigation query{page_text}."

    def _build_snippet(self, content: str, limit: int = 260) -> str:
        compact = re.sub(r"\s+", " ", content or "").strip()
        if not compact:
            return ""
        snippet = compact[:limit]
        if len(compact) > limit and " " in snippet:
            snippet = snippet.rsplit(" ", 1)[0].strip()
        return f"{snippet}..." if len(compact) > len(snippet) else snippet

    def _read_document_content(self, path: Path) -> str:
        suffix = path.suffix.lower()
        try:
            if suffix in {".txt", ".md", ".log"}:
                return path.read_text(encoding="utf-8", errors="ignore")
            if suffix == ".csv":
                return self.tabular_text_service.extract_text(path)
            if suffix in self.tabular_text_service.SPREADSHEET_SUFFIXES:
                return self.tabular_text_service.extract_text(path)
            if suffix == ".eml":
                return self._read_eml(path)
            if suffix == ".docx":
                return self._read_docx(path)
            if suffix == ".pdf":
                return self._read_pdf(path)
        except Exception:
            return ""
        return ""

    def _infer_section_title(self, content: str) -> str:
        normalized = re.sub(r"\r", "\n", content or "")
        lines = [line.strip() for line in normalized.splitlines() if line.strip()]
        for line in lines[:8]:
            compact = re.sub(r"\s+", " ", line).strip()
            if 4 <= len(compact) <= 120:
                if compact.endswith(":"):
                    return compact.rstrip(":").strip()
                if re.match(r"^[A-Z0-9][A-Za-z0-9 \-/&,().]+$", compact):
                    return compact
        return lines[0][:120] if lines else ""

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
