from __future__ import annotations

from typing import Any

from app.services.risk_scoring_service import RiskScoringService
from app.services.recommendation_service import RecommendationService
from app.services.finding_generation_service import FindingGenerationService
from app.services.response_evaluation_service import ResponseEvaluationService


class ResponseComposerService:
    def __init__(self) -> None:
        self.finding_service = FindingGenerationService()
        self.risk_scoring_service = RiskScoringService()
        self.recommendation_service = RecommendationService()
        self.response_evaluation_service = ResponseEvaluationService()

    def compose(self, response_contract: dict[str, Any]) -> dict[str, Any]:
        structured_evidence = list(response_contract.get("structured_evidence", []))
        document_evidence = list(response_contract.get("document_evidence", []))
        intent = response_contract.get("intent", {})
        query = response_contract.get("query", "")

        finding = response_contract.get("finding")
        if not (isinstance(finding, dict) and finding):
            finding = self.finding_service.generate(
                structured_evidence=structured_evidence,
                document_evidence=document_evidence,
                intent=intent,
                query=query,
                citations=list(response_contract.get("citations", [])),
                investigation_context=self._build_investigation_context(response_contract),
            )
        finding = self._normalize_finding(finding)
        risk = self.risk_scoring_service.score(
            finding=finding,
            structured_evidence=structured_evidence,
            document_evidence=document_evidence,
        )
        response_contract["risk_rating"] = risk["risk_rating"]
        response_contract["risk_score"] = risk["risk_score"]
        response_contract["risk_drivers"] = risk["risk_drivers"]
        if response_contract.get("success", True) and not finding.get("recommendation"):
            finding["recommendation"] = self.recommendation_service.recommend(
                finding_title=str(finding.get("finding_title", "")),
                structured_evidence=structured_evidence,
                document_evidence=document_evidence,
            )
        if not response_contract.get("recommendations") and finding.get("recommendation"):
            response_contract["recommendations"] = [finding.get("recommendation")]

        reasoning = list(response_contract.get("traceability", {}).get("reasoning_path", []))
        if not reasoning:
            reasoning = [
                "Intent was extracted from the user query.",
                "Agents were invoked based on the extracted intent.",
                "Structured evidence and document evidence were combined.",
                "Deterministic finding generation was applied to the aggregated evidence.",
            ]

        supporting_documents = (
            response_contract.get("supporting_documents")
            or finding.get("supporting_documents", [])
            or document_evidence
        )
        response_contract["supporting_documents"] = supporting_documents
        response_contract["citations"] = self._build_citations(document_evidence or supporting_documents)
        response_contract["navigation_payloads"] = self._build_navigation_payloads(response_contract["citations"])
        supporting_summary = self._format_supporting_documents(supporting_documents)
        supporting_section = self._build_supporting_section(supporting_documents)
        if response_contract.get("entity_type") == "vendor":
            final_response = self._build_vendor_narrative(
                query=query,
                intent=intent,
                risk_rating=risk["risk_rating"],
                risk_drivers=risk["risk_drivers"],
                investigation_summary=str(
                    response_contract.get("investigation_summary")
                    or response_contract.get("vendor_summary")
                    or finding.get("finding_summary", "")
                ),
                investigation_metrics=dict(response_contract.get("investigation_metrics", {})),
                key_findings=list(response_contract.get("key_findings", [])),
                top_supporting_evidence=list(response_contract.get("top_supporting_evidence", [])),
                supporting_evidence=list(response_contract.get("supporting_evidence", [])),
                supporting_summary=supporting_summary,
                supporting_section=supporting_section,
                recommendations=list(response_contract.get("recommendations", [])),
                traceability=response_contract.get("traceability", {}),
                narrative=str(finding.get("narrative") or ""),
            )
        elif response_contract.get("entity_type") == "transaction":
            final_response = self._build_transaction_narrative(
                query=query,
                intent=intent,
                risk_rating=risk["risk_rating"],
                risk_drivers=risk["risk_drivers"],
                transaction_summary=str(
                    response_contract.get("investigation_summary")
                    or response_contract.get("transaction_summary")
                    or finding.get("finding_summary", "")
                ),
                investigation_metrics=dict(response_contract.get("investigation_metrics", {})),
                key_findings=list(response_contract.get("key_findings", [])),
                top_supporting_evidence=list(response_contract.get("top_supporting_evidence", [])),
                supporting_evidence=list(response_contract.get("supporting_evidence", [])),
                supporting_summary=supporting_summary,
                supporting_section=supporting_section,
                recommendations=list(response_contract.get("recommendations", [])),
                traceability=response_contract.get("traceability", {}),
                narrative=str(finding.get("narrative") or ""),
            )
        elif response_contract.get("investigation_plan"):
            final_response = self._build_investigation_narrative(
                query=query,
                intent=intent,
                risk_rating=risk["risk_rating"],
                risk_drivers=risk["risk_drivers"],
                investigation_plan=dict(response_contract.get("investigation_plan", {})),
                entities_investigated=list(response_contract.get("entities_investigated", [])),
                investigation_summary=str(response_contract.get("investigation_summary") or finding.get("finding_summary", "")),
                investigation_metrics=dict(response_contract.get("investigation_metrics", {})),
                key_findings=list(response_contract.get("key_findings", [])),
                top_supporting_evidence=list(response_contract.get("top_supporting_evidence", [])),
                supporting_evidence=list(response_contract.get("supporting_evidence", [])),
                supporting_summary=supporting_summary,
                supporting_section=supporting_section,
                recommendations=list(response_contract.get("recommendations", [])),
                traceability=response_contract.get("traceability", {}),
                narrative=str(finding.get("narrative") or ""),
            )
        else:
            final_response = self._build_narrative(
                query=query,
                intent=intent,
                risk_rating=risk["risk_rating"],
                risk_drivers=risk["risk_drivers"],
                finding=finding,
                supporting_summary=supporting_summary,
                supporting_section=supporting_section,
                narrative=str(finding.get("narrative") or ""),
            )

        response_contract["finding"] = finding
        response_contract["reasoning"] = reasoning
        if document_evidence:
            response_contract["document_intelligence_summary"] = self._build_document_intelligence_summary(document_evidence)
        response_contract["final_response"] = final_response
        response_contract["evaluation"] = self.response_evaluation_service.evaluate(
            query=query,
            response_contract=response_contract,
        )
        return response_contract

    def _format_supporting_documents(self, supporting_documents: list[dict[str, Any]]) -> str:
        if not supporting_documents:
            return "None"
        lines = []
        for document in supporting_documents:
            doc_id = document.get("document_id") or "unknown"
            file_name = document.get("file_name") or doc_id
            source_uri = document.get("source_uri") or "n/a"
            chunk_id = document.get("chunk_id")
            page_number = document.get("page_number")
            section_title = document.get("section_title")
            anchor_text = document.get("anchor_text")
            start_offset = document.get("start_offset")
            end_offset = document.get("end_offset")
            linked_transaction = document.get("linked_transaction") or "n/a"
            reason_selected = document.get("reason_selected") or "n/a"
            content_snippet = document.get("content_snippet") or document.get("content") or "n/a"
            citation_text = document.get("citation_text") or content_snippet
            relevance_score = document.get("relevance_score")
            citation_bits = [f"Doc: {file_name}"]
            if page_number not in (None, ""):
                citation_bits.append(f"Page: {page_number}")
            if section_title:
                citation_bits.append(f"Section: {section_title}")
            if anchor_text:
                citation_bits.append(f"Anchor: {anchor_text}")
            if start_offset is not None or end_offset is not None:
                citation_bits.append(f"Offsets: {start_offset if start_offset is not None else 'n/a'}-{end_offset if end_offset is not None else 'n/a'}")
            citation_bits.append(f"Evidence: {citation_text}")
            if chunk_id:
                lines.append(
                    f"{doc_id} / {chunk_id} (Score: {relevance_score if relevance_score is not None else 'n/a'}; Linked Transaction: {linked_transaction}; Source URI: {source_uri}; Reason: {reason_selected}; {'; '.join(citation_bits)})"
                )
            else:
                lines.append(
                    f"{doc_id} (Linked Transaction: {linked_transaction}; Source URI: {source_uri}; Reason: {reason_selected}; {'; '.join(citation_bits)})"
                )
        return "; ".join(lines)

    def _build_supporting_section(self, supporting_documents: list[dict[str, Any]]) -> str:
        if not supporting_documents:
            return "None"
        lines = []
        for document in supporting_documents:
            block = [
                f"Document ID: {document.get('document_id', '')}",
            ]
            if document.get("file_name"):
                block.append(f"File Name: {document.get('file_name', '')}")
            if document.get("chunk_id"):
                block.append(f"Chunk ID: {document.get('chunk_id', '')}")
            if document.get("relevance_score") is not None:
                block.append(f"Retrieval Score: {document.get('relevance_score', '')}")
            if document.get("source_uri"):
                block.append(f"Source URI: {document.get('source_uri', '')}")
            if document.get("page_number") not in (None, ""):
                block.append(f"Page Number: {document.get('page_number', '')}")
            if document.get("section_title"):
                block.append(f"Section Title: {document.get('section_title', '')}")
            if document.get("anchor_text"):
                block.append(f"Anchor Text: {document.get('anchor_text', '')}")
            if document.get("start_offset") is not None or document.get("end_offset") is not None:
                block.append(
                    f"Offsets: {document.get('start_offset', 'n/a')}-{document.get('end_offset', 'n/a')}"
                )
            block.extend(
                [
                    f"Linked Transaction: {document.get('linked_transaction', '')}",
                    f"Citation Text: {document.get('citation_text', '') or document.get('content_snippet', '') or document.get('content', '')}",
                    f"Reason Selected: {document.get('reason_selected', '')}",
                ]
            )
            lines.append("\n".join(block))
        return "\n\n".join(lines)

    def _build_citations(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for document in documents:
            if document.get("page_number") in (None, "") and not document.get("citation_text") and not document.get("content_snippet"):
                continue
            file_name = document.get("file_name") or document.get("document_id") or ""
            source_type = document.get("source_type") or document.get("document_type") or document.get("document_category") or ""
            linked_transaction = document.get("linked_transaction") or document.get("transaction_id")
            related_vendor_id = document.get("related_vendor_id") or document.get("vendor_id")
            selection_exp = document.get("selection_explanation")
            if not isinstance(selection_exp, dict):
                selection_exp = None
            citations.append(
                {
                    "document_id": document.get("document_id"),
                    "file_name": file_name,
                    "document_name": document.get("document_name") or file_name,
                    "source_uri": document.get("source_uri"),
                    "source_type": source_type,
                    "page_number": document.get("page_number"),
                    "section_title": document.get("section_title"),
                    "anchor_text": document.get("anchor_text"),
                    "start_offset": document.get("start_offset"),
                    "end_offset": document.get("end_offset"),
                    "chunk_id": document.get("chunk_id"),
                    "citation_text": document.get("citation_text") or document.get("content_snippet") or document.get("content"),
                    "relevance_score": document.get("relevance_score"),
                    "linked_transaction": linked_transaction,
                    "related_vendor_id": related_vendor_id,
                    "citation_origin": document.get("citation_origin") or "document_evidence",
                    "selection_explanation": selection_exp,
                    "selection_reason": document.get("reason_selected") or (selection_exp or {}).get("selection_reason"),
                    "supports": document.get("supports") or (selection_exp or {}).get("supports"),
                    "relevance_summary": document.get("relevance_summary") or (selection_exp or {}).get("relevance_summary"),
                    "confidence_note": document.get("confidence_note") or (selection_exp or {}).get("confidence_note"),
                }
            )
        return citations

    def _build_navigation_payloads(self, citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for citation in citations:
            payloads.append(
                {
                    "document_id": citation.get("document_id"),
                    "file_name": citation.get("file_name"),
                    "source_uri": citation.get("source_uri"),
                    "page_number": citation.get("page_number"),
                    "section_title": citation.get("section_title"),
                    "anchor_text": citation.get("anchor_text"),
                    "start_offset": citation.get("start_offset"),
                    "end_offset": citation.get("end_offset"),
                    "chunk_id": citation.get("chunk_id"),
                    "citation_text": citation.get("citation_text"),
                }
            )
        return payloads

    def _build_narrative(
        self,
        *,
        query: str,
        intent: dict[str, Any],
        risk_rating: str,
        risk_drivers: list[str],
        finding: dict[str, Any],
        supporting_summary: str,
        supporting_section: str,
        narrative: str = "",
    ) -> str:
        risk_driver_text = "\n".join(f"- {driver}" for driver in risk_drivers) if risk_drivers else "None"
        return (
            f"Narrative:\n{narrative}\n\n" if narrative else ""
        ) + (
            f"Finding: {finding.get('finding_summary', '')}\n"
            f"Risk Rating: {risk_rating}\n"
            f"Risk Drivers:\n{risk_driver_text}\n"
            f"Evidence Summary: {finding.get('evidence_summary', '')}\n"
            f"Supporting Documents: {supporting_summary}\n"
            f"{supporting_section}\n"
            f"Recommendation: {finding.get('recommendation', '')}\n"
            f"Query: {query}\n"
            f"Intent: {intent.get('intent') or 'unsupported'}"
        )

    def _build_vendor_narrative(
        self,
        *,
        query: str,
        intent: dict[str, Any],
        risk_rating: str,
        risk_drivers: list[str],
        investigation_summary: str,
        investigation_metrics: dict[str, int],
        key_findings: list[str],
        top_supporting_evidence: list[dict[str, Any]],
        supporting_evidence: list[dict[str, Any]],
        supporting_summary: str,
        supporting_section: str,
        recommendations: list[str],
        traceability: dict[str, Any],
        narrative: str = "",
    ) -> str:
        risk_driver_text = "\n".join(f"- {driver}" for driver in risk_drivers) if risk_drivers else "None"
        key_finding_text = "\n".join(f"- {finding}" for finding in key_findings) if key_findings else "None"
        metrics_text = self._format_metrics(investigation_metrics)
        top_evidence_text = self._format_top_supporting_evidence(top_supporting_evidence)
        evidence_text = self._format_evidence_summary_items(supporting_evidence)
        recommendation_text = "\n".join(f"- {item}" for item in recommendations) if recommendations else "None"
        return (
            "Vendor Investigation Report\n\n"
            + (f"Narrative:\n{narrative}\n\n" if narrative else "")
            + (
            f"Executive Summary:\n{investigation_summary}\n\n"
            f"Investigation Metrics:\n{metrics_text}\n\n"
            f"Risk Rating: {risk_rating}\n"
            f"Risk Drivers:\n{risk_driver_text}\n"
            f"Key Findings:\n{key_finding_text}\n"
            f"Top Supporting Evidence:\n{top_evidence_text}\n"
            f"Supporting Evidence:\n{evidence_text}\n"
            f"Supporting Documents: {supporting_summary}\n"
            f"{supporting_section}\n"
            f"Recommendations:\n{recommendation_text}\n"
            f"{self._format_traceability(traceability)}\n"
            f"Query: {query}\n"
            f"Intent: {intent.get('intent') or 'vendor_investigation'}"
            )
        )

    def _build_transaction_narrative(
        self,
        *,
        query: str,
        intent: dict[str, Any],
        risk_rating: str,
        risk_drivers: list[str],
        transaction_summary: str,
        investigation_metrics: dict[str, int],
        key_findings: list[str],
        top_supporting_evidence: list[dict[str, Any]],
        supporting_evidence: list[dict[str, Any]],
        supporting_summary: str,
        supporting_section: str,
        recommendations: list[str],
        traceability: dict[str, Any],
        narrative: str = "",
    ) -> str:
        risk_driver_text = "\n".join(f"- {driver}" for driver in risk_drivers) if risk_drivers else "None"
        key_finding_text = "\n".join(f"- {finding}" for finding in key_findings) if key_findings else "None"
        metrics_text = self._format_transaction_metrics(investigation_metrics)
        top_evidence_text = self._format_top_supporting_evidence(top_supporting_evidence)
        evidence_text = self._format_evidence_summary_items(supporting_evidence)
        recommendation_text = "\n".join(f"- {item}" for item in recommendations) if recommendations else "None"
        return (
            "Transaction Investigation Report\n\n"
            + (f"Narrative:\n{narrative}\n\n" if narrative else "")
            + (
            f"Executive Summary:\n{transaction_summary}\n\n"
            f"Investigation Metrics:\n{metrics_text}\n\n"
            f"Risk Assessment: {risk_rating}\n"
            f"Risk Drivers:\n{risk_driver_text}\n"
            f"Key Findings:\n{key_finding_text}\n"
            f"Top Supporting Evidence:\n{top_evidence_text}\n"
            f"Supporting Evidence:\n{evidence_text}\n"
            f"Supporting Documents: {supporting_summary}\n"
            f"{supporting_section}\n"
            f"Recommendations:\n{recommendation_text}\n"
            f"{self._format_traceability(traceability)}\n"
            f"Query: {query}\n"
            f"Intent: {intent.get('intent') or 'transaction_investigation'}"
            )
        )

    def _build_investigation_narrative(
        self,
        *,
        query: str,
        intent: dict[str, Any],
        risk_rating: str,
        risk_drivers: list[str],
        investigation_plan: dict[str, Any],
        entities_investigated: list[str],
        investigation_summary: str,
        investigation_metrics: dict[str, int],
        key_findings: list[str],
        top_supporting_evidence: list[dict[str, Any]],
        supporting_evidence: list[dict[str, Any]],
        supporting_summary: str,
        supporting_section: str,
        recommendations: list[str],
        traceability: dict[str, Any],
        narrative: str = "",
    ) -> str:
        agents_selected = investigation_plan.get("agents_required", [])
        reasoning = investigation_plan.get("reasoning", [])
        risk_driver_text = "\n".join(f"- {driver}" for driver in risk_drivers) if risk_drivers else "None"
        reasoning_text = "\n".join(f"- {item}" for item in reasoning) if reasoning else "None"
        entities_text = "\n".join(f"- {item}" for item in entities_investigated) if entities_investigated else "None"
        key_finding_text = "\n".join(f"- {finding}" for finding in key_findings) if key_findings else "None"
        plan_text = "\n".join(f"- {agent}" for agent in agents_selected) if agents_selected else "None"
        metrics_text = self._format_metrics(investigation_metrics)
        top_evidence_text = self._format_top_supporting_evidence(top_supporting_evidence)
        evidence_text = self._format_evidence_summary_items(supporting_evidence)
        recommendation_text = "\n".join(f"- {item}" for item in recommendations) if recommendations else "None"
        return (
            "Investigation Report\n\n"
            + (f"Narrative:\n{narrative}\n\n" if narrative else "")
            + (
            "Investigation Plan\n"
            f"Agents Selected:\n{plan_text}\n"
            f"Reasoning:\n{reasoning_text}\n\n"
            f"Entities Investigated:\n{entities_text}\n\n"
            f"Executive Summary:\n{investigation_summary}\n\n"
            f"Investigation Metrics:\n{metrics_text}\n\n"
            f"Risk Assessment: {risk_rating}\n"
            f"Risk Drivers:\n{risk_driver_text}\n"
            f"Key Findings:\n{key_finding_text}\n"
            f"Top Supporting Evidence:\n{top_evidence_text}\n"
            f"Supporting Evidence:\n{evidence_text}\n"
            f"Supporting Documents: {supporting_summary}\n"
            f"{supporting_section}\n"
            f"Recommendations:\n{recommendation_text}\n"
            f"{self._format_traceability(traceability)}\n"
            f"Query: {query}\n"
            f"Intent: {intent.get('intent') or 'investigation'}"
            )
        )

    def _build_document_intelligence_summary(self, document_evidence: list[dict[str, Any]]) -> str:
        summary_counts: dict[str, int] = {}
        signal_counts: dict[str, int] = {}
        for document in document_evidence:
            intelligence = document.get("document_intelligence")
            if not isinstance(intelligence, dict):
                continue
            doc_type = intelligence.get("document_type") or "Unknown"
            summary_counts[doc_type] = summary_counts.get(doc_type, 0) + 1
            for signal in intelligence.get("signals", []):
                signal_counts[signal] = signal_counts.get(signal, 0) + 1

        type_text = ", ".join(f"{count} {doc_type.lower()}" for doc_type, count in summary_counts.items()) or "No classified documents"
        signal_text = ", ".join(f"{count} {signal}" for signal, count in signal_counts.items()) or "No document signals identified"
        return f"Document Intelligence Summary: {type_text}. Signals: {signal_text}."

    def _format_evidence_summary_items(self, supporting_evidence: list[dict[str, Any]]) -> str:
        if not supporting_evidence:
            return "None"
        return "\n".join(
            f"- {item.get('summary', 'n/a')}" for item in supporting_evidence if item.get("summary")
        ) or "None"

    def _format_metrics(self, metrics: dict[str, int]) -> str:
        if not metrics:
            return "None"
        labels = [
            ("transactions_reviewed", "Transactions Reviewed"),
            ("contracts_reviewed", "Contracts Reviewed"),
            ("documents_reviewed", "Documents Reviewed"),
            ("flagged_transactions", "Flagged Transactions"),
        ]
        lines = [f"- {label}: {metrics.get(key, 0)}" for key, label in labels]
        return "\n".join(lines)

    def _format_transaction_metrics(self, metrics: dict[str, int]) -> str:
        if not metrics:
            return "None"
        labels = [
            ("documents_reviewed", "Documents Reviewed"),
            ("findings_reviewed", "Findings Reviewed"),
            ("evidence_records", "Evidence Records"),
            ("linked_entities", "Linked Entities"),
        ]
        lines = [f"- {label}: {metrics.get(key, 0)}" for key, label in labels]
        return "\n".join(lines)

    def _format_top_supporting_evidence(self, top_supporting_evidence: list[dict[str, Any]]) -> str:
        if not top_supporting_evidence:
            return "None"
        lines = []
        for index, item in enumerate(top_supporting_evidence, start=1):
            document_id = item.get("document_id") or "unknown"
            file_name = item.get("file_name") or document_id
            source_uri = item.get("source_uri") or "n/a"
            chunk_id = item.get("chunk_id")
            page_number = item.get("page_number")
            section_title = item.get("section_title")
            anchor_text = item.get("anchor_text")
            start_offset = item.get("start_offset")
            end_offset = item.get("end_offset")
            category = item.get("document_category") or "n/a"
            priority = item.get("priority", "n/a")
            reason = item.get("reason_selected") or "n/a"
            snippet = item.get("content_snippet") or item.get("content") or "n/a"
            citation_text = item.get("citation_text") or snippet
            score = item.get("relevance_score")
            chunk_text = f" / {chunk_id}" if chunk_id else ""
            score_text = f" | Score {score}" if score is not None else ""
            citation_text_bits = [f"File: {file_name}"]
            citation_text_bits.append(f"Source URI {source_uri}")
            if page_number not in (None, ""):
                citation_text_bits.append(f"Page {page_number}")
            if section_title:
                citation_text_bits.append(f"Section {section_title}")
            if anchor_text:
                citation_text_bits.append(f"Anchor {anchor_text}")
            if start_offset is not None or end_offset is not None:
                citation_text_bits.append(
                    f"Offsets {start_offset if start_offset is not None else 'n/a'}-{end_offset if end_offset is not None else 'n/a'}"
                )
            citation_text_bits.append(f"Citation {citation_text}")
            lines.append(
                f"{index}. {document_id}{chunk_text} [{category}] (Priority {priority}{score_text}) - {reason} - {'; '.join(citation_text_bits)}"
            )
        return "\n".join(lines)

    def _format_traceability(self, traceability: dict[str, Any]) -> str:
        if not traceability:
            return "Traceability:\nNone"
        agents = ", ".join(traceability.get("agents_invoked", [])) or "None"
        sources = ", ".join(traceability.get("sources_used", [])) or "None"
        reasoning = traceability.get("reasoning_path", [])
        reasoning_text = "\n".join(f"- {item}" for item in reasoning) if reasoning else "None"
        return (
            "Traceability:\n"
            f"Agents Used: {agents}\n"
            f"Sources Used: {sources}\n"
            f"Reasoning Path:\n{reasoning_text}"
        )

    def _normalize_finding(self, finding: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(finding)
        title = str(normalized.get("title") or normalized.get("finding_title") or "Evidence Retrieved").strip()
        summary = str(normalized.get("summary") or normalized.get("finding_summary") or "").strip()
        recommendation = str(normalized.get("recommendation") or "").strip()
        narrative = str(normalized.get("narrative") or "").strip()
        if not narrative:
            narrative = self._build_narrative(
                query=str(normalized.get("query") or ""),
                intent=normalized.get("intent") if isinstance(normalized.get("intent"), dict) else {},
                risk_rating=str(normalized.get("risk_rating") or "LOW"),
                risk_drivers=list(normalized.get("risk_drivers", [])) if isinstance(normalized.get("risk_drivers"), list) else [],
                finding=normalized,
                supporting_summary=str(normalized.get("supporting_summary") or normalized.get("evidence_summary") or ""),
                supporting_section=str(normalized.get("supporting_section") or ""),
            )
        normalized.update(
            {
                "title": title,
                "finding_title": title,
                "summary": summary,
                "finding_summary": summary,
                "recommendation": recommendation,
                "narrative": narrative,
                "risk_reasoning": str(normalized.get("risk_reasoning") or normalized.get("evidence_summary") or "").strip(),
            }
        )
        return normalized

    def _build_investigation_context(self, response_contract: dict[str, Any]) -> dict[str, Any]:
        traceability = response_contract.get("traceability", {})
        context = {
            "entity_type": response_contract.get("entity_type"),
            "entity_id": response_contract.get("entity_id"),
            "agents_used": list(response_contract.get("agents_used", [])),
            "sources": list(response_contract.get("sources", [])),
            "traceability": traceability if isinstance(traceability, dict) else {},
            "investigation_plan": response_contract.get("investigation_plan", {}),
            "investigation_summary": response_contract.get("investigation_summary", ""),
            "key_findings": list(response_contract.get("key_findings", [])),
            "top_supporting_evidence": list(response_contract.get("top_supporting_evidence", [])),
            "supporting_documents": list(response_contract.get("supporting_documents", [])),
            "investigation_metrics": dict(response_contract.get("investigation_metrics", {})),
        }
        if response_contract.get("document_intelligence_summary"):
            context["document_intelligence_summary"] = response_contract.get("document_intelligence_summary")
        if response_contract.get("policy_context"):
            context["policy_context"] = response_contract.get("policy_context")
        return context
