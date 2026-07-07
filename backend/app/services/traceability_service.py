from __future__ import annotations

from typing import Any


class TraceabilityService:
    def initialize(self) -> dict[str, Any]:
        return {
            "agents_invoked": [],
            "agent_selection_reasoning": [],
            "sources_used": [],
            "evidence_used": [],
            "reasoning_path": [],
            "langfuse": {
                "enabled": False,
                "trace_id": None,
                "trace_url": None,
                "session_id": None,
            },
        }

    def record_agent(self, traceability: dict[str, Any], agent: str, reason: str) -> None:
        self._append_unique(traceability, "agents_invoked", agent)
        self._append_unique(traceability, "agent_selection_reasoning", reason)

    def record_source(self, traceability: dict[str, Any], source: str) -> None:
        self._append_unique(traceability, "sources_used", source)

    def record_evidence(self, traceability: dict[str, Any], evidence: dict[str, Any]) -> None:
        traceability.setdefault("evidence_used", []).append(evidence)

    def record_reasoning(self, traceability: dict[str, Any], reasoning: str) -> None:
        self._append_unique(traceability, "reasoning_path", reasoning)

    def attach_langfuse(
        self,
        traceability: dict[str, Any],
        *,
        enabled: bool,
        trace_id: str | None = None,
        trace_url: str | None = None,
        session_id: str | None = None,
    ) -> None:
        traceability["langfuse"] = {
            "enabled": enabled,
            "trace_id": trace_id,
            "trace_url": trace_url,
            "session_id": session_id,
        }

    def _append_unique(self, traceability: dict[str, Any], key: str, value: str) -> None:
        items = traceability.setdefault(key, [])
        if value and value not in items:
            items.append(value)
