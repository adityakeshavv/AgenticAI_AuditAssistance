from __future__ import annotations

from typing import Any


class EvidenceAggregatorService:
    def aggregate(
        self,
        *,
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
        sources: list[str],
    ) -> dict[str, Any]:
        merged_sources: list[str] = []
        for source in sources:
            if source not in merged_sources:
                merged_sources.append(source)

        return {
            "structured_evidence": structured_evidence,
            "document_evidence": document_evidence,
            "sources": merged_sources,
        }
