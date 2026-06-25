from __future__ import annotations

from typing import Any


class BaseInvestigationService:
    EVIDENCE_PRIORITY = {
        "investigation_reports": 1,
        "investigation_report": 1,
        "emails": 2,
        "email": 2,
        "audit_reports": 3,
        "audit_report": 3,
        "approval_emails": 4,
        "approval_email": 4,
        "meeting_minutes": 5,
        "meeting_minute": 5,
    }

    def calculate_metrics(
        self,
        *,
        transactions: list[dict[str, Any]],
        contracts: list[dict[str, Any]],
        documents: list[dict[str, Any]],
    ) -> dict[str, int]:
        flagged_transactions = sum(1 for row in transactions if str(row.get("status", "")).upper() == "FLAGGED")
        return {
            "transactions_reviewed": len(transactions),
            "contracts_reviewed": len(contracts),
            "documents_reviewed": len(documents),
            "flagged_transactions": flagged_transactions,
        }

    def build_summary(
        self,
        *,
        entity_type: str,
        entity_id: str,
        entity_name: str | None,
        risk_rating: str,
        risk_drivers: list[str],
        key_findings: list[str],
        metrics: dict[str, int],
    ) -> str:
        display_name = f"{entity_id} ({entity_name})" if entity_name else entity_id
        summary_parts = [
            f"{entity_type.title()} {display_name} was reviewed using transaction activity, contract relationships, supporting audit evidence and linked documents.",
            f"Investigation coverage included {metrics.get('transactions_reviewed', 0)} transaction(s), {metrics.get('contracts_reviewed', 0)} contract(s) and {metrics.get('documents_reviewed', 0)} document(s).",
        ]
        if metrics.get("flagged_transactions", 0):
            summary_parts.append(
                f"{metrics['flagged_transactions']} flagged transaction(s) were identified during the review."
            )
        if key_findings:
            summary_parts.append("Key findings indicate " + "; ".join(key_findings[:2]).rstrip(".") + ".")
        if risk_drivers:
            summary_parts.append(f"Based on the evidence reviewed, the {entity_type} is assessed as {risk_rating} risk.")
        return " ".join(summary_parts)

    def build_findings(
        self,
        *,
        entity_type: str,
        transactions: list[dict[str, Any]],
        contracts: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        documents: list[dict[str, Any]],
        risk_drivers: list[str],
    ) -> list[str]:
        key_findings: list[str] = []
        flagged_transactions = [row for row in transactions if str(row.get("status", "")).upper() == "FLAGGED"]
        high_risk_transactions = [row for row in transactions if float(row.get("risk_score") or 0) > 0.8]
        expired_contracts = [row for row in contracts if str(row.get("status", "")).upper() == "EXPIRED"]

        if flagged_transactions:
            key_findings.append(f"{len(flagged_transactions)} flagged transaction(s) identified for the {entity_type}.")
        if high_risk_transactions:
            key_findings.append(f"{len(high_risk_transactions)} transaction(s) exceeded risk threshold 0.8.")
        if expired_contracts:
            key_findings.append(f"{len(expired_contracts)} expired contract(s) identified.")
        if findings:
            titles = ", ".join(
                f"{finding.get('finding_id')} ({finding.get('severity')})"
                for finding in findings[:3]
                if finding.get("finding_id")
            )
            if titles:
                key_findings.append(f"Linked finding(s) retrieved: {titles}.")
        if documents:
            key_findings.append(f"{len(documents)} supporting document(s) retrieved.")
        if risk_drivers:
            key_findings.append("Risk drivers: " + "; ".join(risk_drivers[:3]))
        return key_findings

    def build_recommendations(
        self,
        *,
        entity_type: str,
        transactions: list[dict[str, Any]],
        contracts: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        risk_rating: str,
    ) -> list[str]:
        recommendations: list[str] = []

        if any(str(row.get("status", "")).upper() == "FLAGGED" for row in transactions):
            recommendations.append(f"Review {entity_type} approval workflow and payment controls.")
        if any(float(row.get("risk_score") or 0) > 0.8 for row in transactions):
            recommendations.append(f"Prioritize review of high-risk {entity_type} transactions.")
        if any(str(row.get("status", "")).upper() == "EXPIRED" for row in contracts):
            recommendations.append(f"Renew or renegotiate expired {entity_type} contracts before further spend.")
        if findings:
            recommendations.append("Review linked audit findings and follow up on unresolved issues.")
        if risk_rating in {"HIGH", "CRITICAL"}:
            recommendations.append(f"Escalate the {entity_type} for targeted audit review.")
        if not recommendations:
            recommendations.append(f"Continue periodic {entity_type} monitoring.")

        return list(dict.fromkeys(recommendations))

    def prioritize_supporting_evidence(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ranked_documents = sorted(
            enumerate(documents),
            key=lambda item: (
                self.EVIDENCE_PRIORITY.get(str(item[1].get("document_category", "")).strip().lower(), 99),
                -self._document_risk_score(item[1]),
                item[0],
            ),
        )

        prioritized: list[dict[str, Any]] = []
        for _, document in ranked_documents:
            prioritized.append(
                {
                    "document_id": document.get("document_id"),
                    "document_type": document.get("document_type"),
                    "document_category": document.get("document_category"),
                    "linked_transaction": document.get("linked_transaction"),
                    "reason_selected": document.get("reason_selected"),
                    "content_snippet": document.get("content_snippet", ""),
                    "priority": self.EVIDENCE_PRIORITY.get(
                        str(document.get("document_category", "")).strip().lower(),
                        99,
                    ),
                }
            )
        return prioritized

    def _document_risk_score(self, document: dict[str, Any]) -> int:
        category = str(document.get("document_category", "")).strip().lower()
        if category in {"investigation_reports", "emails", "audit_reports"}:
            return 3
        if category in {"approval_emails", "meeting_minutes"}:
            return 2
        return 1
