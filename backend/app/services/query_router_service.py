from __future__ import annotations

import logging
from typing import Any

from agents.router_agent import QueryRouterAgent


logger = logging.getLogger(__name__)


class QueryRoutingService:
    """Small wrapper around the router agent that standardizes routing metadata."""

    def __init__(self, *, confidence_threshold: float = 0.75) -> None:
        self.router = QueryRouterAgent()
        self.confidence_threshold = confidence_threshold

    def route(self, query: str, *, trace_context: Any | None = None) -> dict[str, Any]:
        route_span = trace_context.begin_span(
            "query_routing",
            input_payload={"query": query},
            metadata={"service": "QueryRoutingService"},
        ) if trace_context else None

        try:
            decision = dict(self.router.route(query))
        except Exception as exc:
            logger.warning("Query routing failed; defaulting to planner escalation: %s", exc)
            decision = {
                "agent": "general_agent",
                "confidence": 0.0,
                "reason": f"Routing failed: {exc}",
                "candidate_agents": ["general_agent"],
                "escalate_to_planner": True,
                "decision_source": "fallback_error",
            }

        decision.setdefault("candidate_agents", [decision.get("agent", "general_agent")])
        decision.setdefault("decision_source", "keyword_fallback" if decision.get("agent") else "llm")
        decision["escalate_to_planner"] = bool(
            decision.get("escalate_to_planner")
            or decision.get("agent") == "general_agent"
            or float(decision.get("confidence", 0.0) or 0.0) < self.confidence_threshold
            or len(decision.get("candidate_agents") or []) > 1
        )

        logger.info(
            "Query routing decision: agent=%s confidence=%.2f escalate=%s candidates=%s source=%s",
            decision.get("agent"),
            float(decision.get("confidence", 0.0) or 0.0),
            decision["escalate_to_planner"],
            decision.get("candidate_agents", []),
            decision.get("decision_source"),
        )

        if route_span:
            route_span.finish(
                output=decision,
                metadata={
                    "agent": decision.get("agent"),
                    "confidence": decision.get("confidence"),
                    "escalate_to_planner": decision.get("escalate_to_planner"),
                    "decision_source": decision.get("decision_source"),
                },
            )

        return decision

    def benchmark(
        self,
        queries: list[dict[str, Any]],
        *,
        use_fallback: bool = True,
    ) -> dict[str, Any]:
        route_fn = self.router.fallback_router.route if use_fallback and hasattr(self.router, "fallback_router") else self.router.route
        results: list[dict[str, Any]] = []
        correct = 0
        escalated = 0
        ambiguous = 0
        low_confidence = 0
        fallback_count = 0
        candidate_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        classification_counts: dict[str, int] = {}

        for item in queries:
            query = str(item.get("query") or "").strip()
            expected = item.get("expected_agent")
            routed = dict(route_fn(query))
            classification = self.classify_decision(routed)
            actual = str(routed.get("agent") or "general_agent")
            passed = actual == expected or expected in (routed.get("candidate_agents") or [])
            correct += 1 if passed else 0
            escalated += 1 if routed.get("escalate_to_planner") else 0
            ambiguous += 1 if classification == "ambiguous" else 0
            low_confidence += 1 if classification == "low_confidence" else 0
            fallback_count += 1 if classification == "fallback" else 0
            source = str(routed.get("decision_source") or "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1
            classification_counts[classification] = classification_counts.get(classification, 0) + 1
            for candidate in routed.get("candidate_agents") or []:
                candidate_counts[str(candidate)] = candidate_counts.get(str(candidate), 0) + 1
            results.append(
                {
                    "query": query,
                    "expected_agent": expected,
                    "routed_agent": actual,
                    "candidate_agents": list(routed.get("candidate_agents") or []),
                    "confidence": routed.get("confidence"),
                    "escalate_to_planner": bool(routed.get("escalate_to_planner")),
                    "decision_source": routed.get("decision_source"),
                    "classification": classification,
                    "passed": passed,
                    "reason": routed.get("reason"),
                }
            )

        total = len(results)
        pass_rate = (correct / total) if total else 0.0
        return {
            "total": total,
            "passed": correct,
            "failed": total - correct,
            "pass_rate": round(pass_rate, 3),
            "escalated": escalated,
            "ambiguous": ambiguous,
            "low_confidence": low_confidence,
            "fallback": fallback_count,
            "decision_source_counts": source_counts,
            "classification_counts": classification_counts,
            "candidate_agent_counts": dict(sorted(candidate_counts.items(), key=lambda item: (-item[1], item[0]))),
            "results": results,
            "failed_examples": [item for item in results if not item["passed"]][:5],
            "successful_examples": [item for item in results if item["passed"]][:5],
        }

    @staticmethod
    def classify_decision(decision: dict[str, Any]) -> str:
        if decision.get("escalate_to_planner"):
            return "ambiguous"
        confidence = float(decision.get("confidence", 0.0) or 0.0)
        if confidence < 0.75:
            return "low_confidence"
        if len(decision.get("candidate_agents") or []) > 1:
            return "ambiguous"
        if str(decision.get("decision_source") or "").strip().lower() == "keyword_fallback":
            return "fallback"
        return "clear"
