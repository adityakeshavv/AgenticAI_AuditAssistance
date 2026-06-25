from __future__ import annotations

from typing import Any


class FindingGenerationService:
    def generate(
        self,
        *,
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
        intent: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        amount_filter = self._amount_filter(intent or {})
        flagged_transactions = self._flagged_transactions(structured_evidence)
        investigation_documents = self._investigation_documents(document_evidence)
        audit_reports = self._audit_reports(document_evidence)

        if not structured_evidence and not document_evidence:
            return {
                "finding_title": "No Significant Findings",
                "finding_summary": "No structured evidence or supporting document evidence was found.",
                "evidence_summary": "No evidence was returned by the current query path.",
                "recommendation": "Continue periodic monitoring.",
                "supporting_documents": [],
            }

        if amount_filter and structured_evidence:
            return self._build_amount_based_finding(
                structured_evidence=structured_evidence,
                document_evidence=document_evidence,
                amount_filter=amount_filter,
            )

        if flagged_transactions:
            evidence_summary = self._build_evidence_summary(
                structured_evidence=structured_evidence,
                document_evidence=document_evidence,
                flagged_transactions=flagged_transactions,
                investigation_documents=investigation_documents,
                audit_reports=audit_reports,
            )
            return {
                "finding_title": "Flagged Transactions Detected",
                "finding_summary": self._build_finding_summary(flagged_transactions, audit_reports, investigation_documents),
                "evidence_summary": evidence_summary,
                "recommendation": "",
                "supporting_documents": self._supporting_documents(document_evidence),
            }

        if audit_reports or investigation_documents:
            return {
                "finding_title": "Supporting Audit Documents Retrieved",
                "finding_summary": "Related audit documents were found even though the transaction evidence did not flag a direct issue.",
                "evidence_summary": self._build_document_only_evidence_summary(audit_reports, investigation_documents),
                "recommendation": "",
                "supporting_documents": self._supporting_documents(document_evidence),
            }

        return {
            "finding_title": "Evidence Retrieved",
            "finding_summary": "Relevant evidence was retrieved, but no flagged transactions or supporting audit reports were identified.",
            "evidence_summary": "Structured evidence was found, but it did not meet the deterministic finding rules.",
            "recommendation": "",
            "supporting_documents": self._supporting_documents(document_evidence),
        }

    def _flagged_transactions(self, structured_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [row for row in structured_evidence if str(row.get("status", "")).upper() == "FLAGGED"]

    def _audit_reports(self, document_evidence: list[dict[str, Any]]) -> list[str]:
        report_labels: list[str] = []
        for document in document_evidence:
            document_type = str(document.get("document_type", "")).upper()
            if "AUDIT_REPORT" in document_type or str(document.get("document_category", "")).lower() == "audit_reports":
                label = document.get("file_name") or document.get("document_id")
                if label and label not in report_labels:
                    report_labels.append(str(label))
        return report_labels

    def _investigation_documents(self, document_evidence: list[dict[str, Any]]) -> list[str]:
        labels: list[str] = []
        for document in document_evidence:
            document_type = str(document.get("document_type", "")).upper()
            if "INVESTIGATION" in document_type or str(document.get("document_category", "")).lower() == "investigation_reports":
                label = document.get("file_name") or document.get("document_id")
                if label and label not in labels:
                    labels.append(str(label))
        return labels

    def _supporting_documents(self, document_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        supporting_documents: list[dict[str, Any]] = []
        for document in document_evidence:
            supporting_documents.append(
                {
                    "document_id": document.get("document_id"),
                    "linked_transaction": document.get("linked_transaction"),
                    "reason_selected": document.get("reason_selected"),
                    "content_snippet": document.get("content_snippet", ""),
                }
            )
        return supporting_documents

    def _amount_filter(self, intent: dict[str, Any]) -> dict[str, Any] | None:
        filters = intent.get("filters")
        if not isinstance(filters, dict):
            return None
        amount_filter = filters.get("amount")
        if not isinstance(amount_filter, dict):
            return None
        operator = str(amount_filter.get("operator", "")).strip()
        value = amount_filter.get("value")
        if operator not in {"<", "<=", ">", ">="} or value is None:
            return None
        return {"operator": operator, "value": value}

    def _build_amount_based_finding(
        self,
        *,
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
        amount_filter: dict[str, Any],
    ) -> dict[str, Any]:
        operator = amount_filter["operator"]
        value = amount_filter["value"]
        completed_count = sum(1 for row in structured_evidence if str(row.get("status", "")).upper() == "COMPLETED")
        top_transactions = structured_evidence[:3]
        supporting_documents = self._supporting_documents(document_evidence)

        if operator in {"<", "<="}:
            title = "Low-Value Transactions Identified"
            summary = f"{len(structured_evidence)} transactions below the threshold of {value} were identified."
            recommendation = "Continue monitoring low-value transaction activity. Review the linked escalation email for historical context."
        else:
            title = "High-Value Transactions Identified"
            summary = f"{len(structured_evidence)} transactions above the threshold of {value} were identified."
            recommendation = "Review approval authority and escalation controls."

        evidence_lines = [
            f"{len(structured_evidence)} transactions matched the amount filter.",
        ]
        if completed_count == len(structured_evidence) and structured_evidence:
            evidence_lines.append("All retrieved transactions are completed.")
        if top_transactions:
            top_labels = ", ".join(
                f"{row.get('transaction_id')} ({row.get('amount')})"
                for row in top_transactions
                if row.get("transaction_id")
            )
            if top_labels:
                evidence_lines.append(f"Top 3 transactions: {top_labels}.")
        if supporting_documents:
            evidence_lines.append(f"{len(supporting_documents)} related document(s) were linked.")
            first_document = supporting_documents[0]
            snippet = first_document.get("content_snippet") or ""
            if snippet:
                evidence_lines.append(f"Supporting evidence snippet: {snippet}")

        if any(str(doc.get("document_category", "")).lower() == "emails" for doc in document_evidence):
            evidence_lines.append("One related escalation email was identified.")
            if operator in {"<", "<="}:
                recommendation = (
                    "Continue monitoring low-value transaction activity. Review the linked escalation email for historical context."
                )

        return {
            "finding_title": title,
            "finding_summary": summary,
            "evidence_summary": " ".join(evidence_lines),
            "recommendation": recommendation,
            "supporting_documents": supporting_documents,
        }

    def _build_finding_summary(
        self,
        flagged_transactions: list[dict[str, Any]],
        audit_reports: list[str],
        investigation_documents: list[str],
    ) -> str:
        summary = f"{len(flagged_transactions)} flagged transactions were identified."
        if audit_reports:
            summary += f" Supporting audit reports were linked: {', '.join(audit_reports)}."
        if investigation_documents:
            summary += f" Investigation documents were linked: {', '.join(investigation_documents)}."
        return summary

    def _build_evidence_summary(
        self,
        *,
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
        flagged_transactions: list[dict[str, Any]],
        investigation_documents: list[str],
        audit_reports: list[str],
    ) -> str:
        top_transactions = flagged_transactions[:3]
        top_labels = ", ".join(
            f"{row.get('transaction_id')} ({row.get('amount')})"
            for row in top_transactions
            if row.get("transaction_id")
        )
        parts = [
            f"{len(structured_evidence)} transaction(s) matched the current criteria.",
        ]
        if top_labels:
            parts.append(f"Top 3 transactions: {top_labels}.")
        if document_evidence:
            parts.append(f"{len(document_evidence)} related document(s) were linked.")
        if audit_reports:
            parts.append(f"Audit reports: {', '.join(audit_reports)}.")
        if investigation_documents:
            parts.append(f"Investigation documents: {', '.join(investigation_documents)}.")
        return " ".join(parts)

    def _build_document_only_evidence_summary(self, audit_reports: list[str], investigation_documents: list[str]) -> str:
        parts: list[str] = []
        if audit_reports:
            parts.append(f"Audit reports: {', '.join(audit_reports)}.")
        if investigation_documents:
            parts.append(f"Investigation documents: {', '.join(investigation_documents)}.")
        return " ".join(parts) if parts else "No supporting documents were linked."
