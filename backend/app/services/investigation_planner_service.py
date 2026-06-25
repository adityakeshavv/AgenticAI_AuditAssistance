from __future__ import annotations

import re
from typing import Any


class InvestigationPlannerService:
    def plan(self, query: str) -> dict[str, Any]:
        normalized = query.lower().strip()

        if not normalized:
            return self._unsupported()

        if self._looks_like_vendor_activity(normalized):
            return {
                "investigation_type": "vendor_activity_investigation",
                "entities_required": ["vendor", "transaction", "document"],
                "agents_required": ["vendor_investigation_agent", "transaction_agent", "document_agent"],
                "reasoning": [
                    "Vendor activity review requires transaction analysis.",
                    "Transaction review requires document evidence.",
                    "Supporting evidence is required to justify the investigation findings.",
                ],
            }

        if self._looks_like_approval_exception(normalized):
            return {
                "investigation_type": "approval_exception_investigation",
                "entities_required": ["transaction", "document"],
                "agents_required": ["transaction_agent", "document_agent"],
                "reasoning": [
                    "Approval exceptions are transaction-driven.",
                    "Supporting documents are required to validate the exception.",
                ],
            }

        if self._looks_like_payment_anomaly(normalized):
            return {
                "investigation_type": "payment_anomaly_investigation",
                "entities_required": ["transaction", "document"],
                "agents_required": ["transaction_agent", "document_agent"],
                "reasoning": [
                    "Payment anomalies are best reviewed through transaction evidence.",
                    "Document evidence is required for audit support.",
                ],
            }

        if self._looks_like_vendor_risk(normalized):
            return {
                "investigation_type": "vendor_risk_investigation",
                "entities_required": ["vendor", "transaction", "document"],
                "agents_required": ["vendor_investigation_agent", "transaction_agent", "document_agent"],
                "reasoning": [
                    "Vendor risk review requires transaction activity analysis.",
                    "Supporting documents are needed to explain the risk drivers.",
                ],
            }

        return self._unsupported()

    def build_execution_query(self, query: str) -> str | None:
        normalized = query.lower().strip()
        if self._looks_like_vendor_activity(normalized) or self._looks_like_vendor_risk(normalized):
            return "show suspicious transactions"
        if self._looks_like_approval_exception(normalized):
            return "show flagged transactions"
        if self._looks_like_payment_anomaly(normalized):
            return "show high-risk transactions"
        return None

    def _looks_like_vendor_activity(self, normalized: str) -> bool:
        return bool(
            re.search(r"\binvestigate\b.*\bsuspicious\b.*\bvendor\b", normalized)
            or re.search(r"\bvendor\b.*\bsuspicious\b.*\bactivity\b", normalized)
            or re.search(r"\breview\b.*\bvendor\b.*\brisk\b", normalized)
            or re.search(r"\banalyze\b.*\bvendor\b.*\bactivity\b", normalized)
            or re.search(r"\binvestigate\b.*\bvendor\b.*\bactivity\b", normalized)
        )

    def _looks_like_approval_exception(self, normalized: str) -> bool:
        return bool(re.search(r"\bapproval\b.*\bexception\b|\bexceptions\b.*\bapproval\b", normalized))

    def _looks_like_payment_anomaly(self, normalized: str) -> bool:
        return bool(
            re.search(r"\bpayment\b.*\banomal", normalized)
            or re.search(r"\banomal", normalized)
            or re.search(r"\bpayment\b.*\bsuspicious\b", normalized)
        )

    def _looks_like_vendor_risk(self, normalized: str) -> bool:
        return bool(
            re.search(r"\bvendor\b.*\brisk\b", normalized)
            or re.search(r"\brisk\b.*\bvendor\b", normalized)
            or re.search(r"\binvestigate\b.*\bvendor\b", normalized)
        )

    def _unsupported(self) -> dict[str, Any]:
        return {
            "investigation_type": "unsupported",
            "entities_required": [],
            "agents_required": [],
            "reasoning": [
                "The query could not be mapped to a supported investigation scenario.",
            ],
        }
