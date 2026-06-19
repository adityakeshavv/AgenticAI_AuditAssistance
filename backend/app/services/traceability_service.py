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

    def _append_unique(self, traceability: dict[str, Any], key: str, value: str) -> None:
        items = traceability.setdefault(key, [])
        if value and value not in items:
            items.append(value)
