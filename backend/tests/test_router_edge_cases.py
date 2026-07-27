from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agents.router_agent import KeywordFallbackRouter
from app.services.llm_router_service import LLMRouterService
from app.services.query_router_service import QueryRoutingService


ROUTER_CASES = [
    ("show flagged transactions", "transaction_agent"),
    ("find duplicate invoices", "transaction_agent"),
    ("list suspicious payments above 100000", "transaction_agent"),
    ("show high risk transactions", "transaction_agent"),
    ("show recent flagged transactions", "transaction_agent"),
    ("which vendor has expired certifications", "compliance_agent"),
    ("review supplier contract compliance", "vendor_agent"),
    ("who approved this transaction", "approval_agent"),
    ("show approval workflow exceptions", "approval_agent"),
    ("investigate transaction TXN-12345", "transaction_agent"),
    ("investigate vendor VND-02731", "vendor_agent"),
    ("show audit evidence for this finding", "investigation_agent"),
    ("what policies govern approval limits", "compliance_agent"),
    ("summarize the investigation report", "investigation_agent"),
    ("list transactions for vendor VND-01530", "transaction_agent"),
    ("show supplier risk and payment anomalies", "transaction_agent"),
    ("find compliance violations for vendor VND-00111", "compliance_agent"),
    ("review rejected approvals and flagged expenses", "approval_agent"),
    ("show documents linked to this finding", "investigation_agent"),
    ("which supplier had suspicious payments", "vendor_agent"),
    ("show expense claims without receipts", "expense_agent"),
    ("analyze payment anomalies and vendor risk", "transaction_agent"),
    ("check policy violations for approvals", "compliance_agent"),
    ("who reviewed the workflow", "approval_agent"),
    ("show investigation evidence for vendor risk", "investigation_agent"),
    ("find duplicate invoices for supplier ABC", "transaction_agent"),
    ("which vendor has flagged transactions", "transaction_agent"),
    ("show compliance and approval issues", "compliance_agent"),
    ("analyze transaction and vendor exposure", "transaction_agent"),
    ("review supplier onboarding evidence", "vendor_agent"),
    ("what is the status of this audit finding", "investigation_agent"),
]


def test_keyword_fallback_router_handles_tricky_audit_queries() -> None:
    router = KeywordFallbackRouter()

    for query, expected_agent in ROUTER_CASES:
        result = router.route(query)
        assert result["agent"] == expected_agent or expected_agent in result.get("candidate_agents", []), query
        assert "reason" in result and result["reason"].strip(), query


def test_keyword_fallback_router_escalates_mixed_domain_queries() -> None:
    router = KeywordFallbackRouter()

    result = router.route("show vendor compliance issues for flagged transactions")

    assert result["escalate_to_planner"] is True
    assert len(result["candidate_agents"]) >= 2
    assert "transaction_agent" in result["candidate_agents"]
    assert "vendor_agent" in result["candidate_agents"] or "compliance_agent" in result["candidate_agents"]


def test_keyword_fallback_router_rejects_unrelated_queries() -> None:
    router = KeywordFallbackRouter()

    cases = [
        "which vendor does not go to school",
        "what is the capital of france",
        "tell me a joke",
        "how is the weather today",
        "who won the cricket match",
    ]

    for query in cases:
        result = router.route(query)
        assert result["agent"] == "general_agent", query
        assert result["escalate_to_planner"] is True, query
        assert result["candidate_agents"] == ["general_agent"], query
        assert result["confidence"] < 0.5, query


def test_llm_router_parses_candidate_agents_and_escalation_flags() -> None:
    service = LLMRouterService()
    payload = {
        "agent": "transaction_agent",
        "confidence": 0.81,
        "reason": "Transaction language with amount threshold.",
        "candidate_agents": ["transaction_agent", "investigation_agent"],
        "escalate_to_planner": True,
    }

    parsed = service._parse_response(json.dumps(payload))

    assert parsed["agent"] == "transaction_agent"
    assert parsed["candidate_agents"] == ["transaction_agent", "investigation_agent"]
    assert parsed["escalate_to_planner"] is True


def test_query_routing_service_benchmark_reports_misroute_signals() -> None:
    service = QueryRoutingService()
    summary = service.benchmark(
        [{"query": query, "expected_agent": expected_agent} for query, expected_agent in ROUTER_CASES]
    )

    assert summary["total"] == len(ROUTER_CASES)
    assert summary["failed"] == 0
    assert summary["passed"] == len(ROUTER_CASES)
    assert summary["pass_rate"] == 1.0
    assert summary["escalated"] > 0
    assert summary["ambiguous"] > 0
    assert "keyword_fallback" in summary["decision_source_counts"] or "llm" in summary["decision_source_counts"]
    assert summary["failed_examples"] == []
