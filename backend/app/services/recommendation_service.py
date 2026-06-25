from __future__ import annotations

from typing import Any


class RecommendationService:
    def recommend(
        self,
        *,
        finding_title: str,
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
    ) -> str:
        if not structured_evidence and not document_evidence:
            return "Continue periodic monitoring."

        flagged_transactions = self._flagged_transactions(structured_evidence)
        investigation_documents = self._documents_by_category(document_evidence, {"investigation_reports"})
        audit_documents = self._documents_by_category(document_evidence, {"audit_reports"})

        if not flagged_transactions:
            return "Continue periodic monitoring."

        if investigation_documents:
            return "Escalate for immediate review and confirm the investigation trail."

        if audit_documents:
            return "Review approval workflow and supporting documentation."

        if "approval" in finding_title.lower():
            return "Verify approval authority and escalation controls."

        return "Review approval workflow and supporting documentation."

    def _flagged_transactions(self, structured_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [row for row in structured_evidence if str(row.get("status", "")).upper() == "FLAGGED"]

    def _documents_by_category(self, document_evidence: list[dict[str, Any]], categories: set[str]) -> list[dict[str, Any]]:
        return [
            document
            for document in document_evidence
            if str(document.get("document_category", "")).strip().lower() in categories
        ]
