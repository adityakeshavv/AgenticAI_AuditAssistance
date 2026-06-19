import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.llm_router_service import LLMRouterService


class KeywordFallbackRouter:
    """Deterministic fallback router used when LLM classification is unavailable."""

    def route(self, query: str) -> dict[str, Any]:

        query = query.lower()

        transaction_keywords = [
            "transaction",
            "transactions",
            "payment",
            "payments",
            "fraud",
            "amount",
            "expense",
            "invoice",
            "invoices",
            "duplicate",
            "suspicious",
            "flagged",
        ]

        vendor_keywords = [
            "vendor",
            "supplier",
            "contract"
        ]

        compliance_keywords = [
            "compliance",
            "policy",
            "violation",
            "audit",
            "certification",
            "certifications",
            "certificate",
            "certificates",
            "expired",
        ]

        approval_keywords = [
            "approval",
            "approved",
            "approver",
            "workflow",
            "who approved",
        ]

        investigation_keywords = [
            "investigation",
            "finding",
            "evidence"
        ]

        if any(word in query for word in compliance_keywords):
            return {
                "agent": "compliance_agent",
                "confidence": 0.90,
                "reason": "Keyword fallback matched compliance-related terms.",
            }

        if any(word in query for word in approval_keywords):
            return {
                "agent": "approval_agent",
                "confidence": 0.90,
                "reason": "Keyword fallback matched approval-related terms.",
            }

        if any(word in query for word in transaction_keywords):
            return {
                "agent": "transaction_agent",
                "confidence": 0.90,
                "reason": "Keyword fallback matched transaction-related terms.",
            }

        if any(word in query for word in vendor_keywords):
            return {
                "agent": "vendor_agent",
                "confidence": 0.90,
                "reason": "Keyword fallback matched vendor-related terms.",
            }

        if any(word in query for word in investigation_keywords):
            return {
                "agent": "investigation_agent",
                "confidence": 0.90,
                "reason": "Keyword fallback matched investigation or evidence terms.",
            }

        return {
            "agent": "general_agent",
            "confidence": 0.50,
            "reason": "Keyword fallback did not find a strong domain match.",
        }


class QueryRouterAgent:
    """LLM-powered query router with deterministic keyword fallback."""

    def __init__(self) -> None:
        self.fallback_router = KeywordFallbackRouter()
        self.llm_router = LLMRouterService(fallback_router=self.fallback_router)

    def route(self, query: str) -> dict[str, Any]:
        return self.llm_router.route(query)
