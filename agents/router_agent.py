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
        normalized = self._normalize_query(query)

        agents = self._score_agents(normalized)
        unique_candidates = [agent for agent in agents if agent != "general_agent"]
        if len(unique_candidates) > 1:
            return {
                "agent": unique_candidates[0],
                "confidence": 0.70,
                "reason": "Keyword fallback found multiple possible audit domains; escalation recommended.",
                "candidate_agents": unique_candidates,
                "escalate_to_planner": True,
                "decision_source": "keyword_fallback",
            }

        if unique_candidates:
            selected = unique_candidates[0]
            return {
                "agent": selected,
                "confidence": 0.82,
                "reason": f"Keyword fallback matched {selected.replace('_agent', '').replace('_', ' ')} terms with audit context.",
                "candidate_agents": [selected],
                "escalate_to_planner": False,
                "decision_source": "keyword_fallback",
            }

        return {
            "agent": "general_agent",
            "confidence": 0.35,
            "reason": "Keyword fallback did not find a strong audit-domain match and will escalate to the planner.",
            "candidate_agents": ["general_agent"],
            "escalate_to_planner": True,
            "decision_source": "keyword_fallback",
        }

    @staticmethod
    def _normalize_query(query: str) -> str:
        return " ".join(str(query or "").lower().split())

    def _score_agents(self, query: str) -> list[str]:
        audit_signal = any(word in query for word in self._audit_context_terms())
        transaction_score = self._score_domain(
            query,
            domain_terms=self._transaction_terms(),
            supporting_terms=self._transaction_support_terms(),
            audit_signal=audit_signal,
        )
        vendor_score = self._score_domain(
            query,
            domain_terms=self._vendor_terms(),
            supporting_terms=self._vendor_support_terms(),
            audit_signal=audit_signal,
        )
        compliance_score = self._score_domain(
            query,
            domain_terms=self._compliance_terms(),
            supporting_terms=self._compliance_support_terms(),
            audit_signal=audit_signal,
        )
        approval_score = self._score_domain(
            query,
            domain_terms=self._approval_terms(),
            supporting_terms=self._approval_support_terms(),
            audit_signal=audit_signal,
        )
        expense_score = self._score_domain(
            query,
            domain_terms=self._expense_terms(),
            supporting_terms=self._expense_support_terms(),
            audit_signal=audit_signal,
        )
        investigation_score = self._score_domain(
            query,
            domain_terms=self._investigation_terms(),
            supporting_terms=self._investigation_support_terms(),
            audit_signal=audit_signal,
        )

        candidates = [
            ("transaction_agent", transaction_score),
            ("vendor_agent", vendor_score),
            ("compliance_agent", compliance_score),
            ("approval_agent", approval_score),
            ("expense_agent", expense_score),
            ("investigation_agent", investigation_score),
        ]
        return [agent for agent, score in sorted(candidates, key=lambda item: (-item[1], item[0])) if score >= 2]

    @staticmethod
    def _score_domain(query: str, *, domain_terms: list[str], supporting_terms: list[str], audit_signal: bool) -> int:
        score = sum(1 for term in domain_terms if term in query)
        score += sum(1 for term in supporting_terms if term in query)
        if audit_signal:
            score += 1
        return score

    @staticmethod
    def _audit_context_terms() -> list[str]:
        return [
            "investigate",
            "review",
            "analyze",
            "analyse",
            "show",
            "find",
            "list",
            "flagged",
            "suspicious",
            "duplicate",
            "risk",
            "high risk",
            "low risk",
            "evidence",
            "finding",
            "findings",
            "citation",
            "trace",
            "document",
            "report",
        ]

    @staticmethod
    def _transaction_terms() -> list[str]:
        return [
            "transaction",
            "transactions",
            "payment",
            "payments",
            "amount",
            "invoice",
            "invoices",
            "fraud",
            "expense",
            "duplicate",
            "flagged",
            "suspicious",
        ]

    @staticmethod
    def _transaction_support_terms() -> list[str]:
        return [
            "high value",
            "risk score",
            "approval threshold",
            "duplicate invoice",
            "missing receipt",
            "above",
            "below",
            "greater than",
            "less than",
            "over",
            "under",
            "more than",
            "less than",
            "txn-",
        ]

    @staticmethod
    def _vendor_terms() -> list[str]:
        return [
            "vendor",
            "vendors",
            "supplier",
            "suppliers",
            "contract",
        ]

    @staticmethod
    def _vendor_support_terms() -> list[str]:
        return [
            "risk",
            "profile",
            "activity",
            "onboarding",
            "review",
            "investigate",
            "analyze",
            "analyse",
            "vnd-",
        ]

    @staticmethod
    def _compliance_terms() -> list[str]:
        return [
            "compliance",
            "policy",
            "policies",
            "violation",
            "audit",
            "certification",
            "certifications",
            "certificate",
            "certificates",
            "expired",
        ]

    @staticmethod
    def _compliance_support_terms() -> list[str]:
        return [
            "framework",
            "controls",
            "governance",
            "exception",
            "exceptions",
            "control",
            "policy violation",
            "control breach",
            "approval",
            "approvals",
            "limit",
            "limits",
            "govern",
            "governing",
        ]

    @staticmethod
    def _approval_terms() -> list[str]:
        return [
            "approval",
            "approved",
            "approver",
            "workflow",
        ]

    @staticmethod
    def _approval_support_terms() -> list[str]:
        return [
            "who approved",
            "authority",
            "limit",
            "limits",
            "escalation",
            "missing approval",
            "approval chain",
        ]

    @staticmethod
    def _expense_terms() -> list[str]:
        return [
            "expense",
            "expenses",
            "expense claim",
            "expense claims",
            "receipt",
            "receipts",
            "reimbursement",
            "travel",
        ]

    @staticmethod
    def _expense_support_terms() -> list[str]:
        return [
            "claim",
            "claims",
            "missing receipt",
            "policy",
            "reimburse",
            "reimbursement",
        ]

    @staticmethod
    def _investigation_terms() -> list[str]:
        return [
            "investigation",
            "investigate",
            "finding",
            "findings",
            "evidence",
            "traceability",
            "citation",
            "document",
            "report",
        ]

    @staticmethod
    def _investigation_support_terms() -> list[str]:
        return [
            "summary",
            "supporting",
            "linked",
            "support",
            "audit report",
            "escalation",
            "report",
        ]


class QueryRouterAgent:
    """LLM-powered query router with deterministic keyword fallback."""

    def __init__(self) -> None:
        self.fallback_router = KeywordFallbackRouter()
        self.llm_router = LLMRouterService(fallback_router=self.fallback_router)

    def route(self, query: str) -> dict[str, Any]:
        return self.llm_router.route(query)
