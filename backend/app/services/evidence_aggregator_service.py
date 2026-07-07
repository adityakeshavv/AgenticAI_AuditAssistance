from __future__ import annotations

from typing import Any


class EvidenceAggregatorService:
    def aggregate(
        self,
        *,
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
        sources: list[str],
        trace_context: Any | None = None,
    ) -> dict[str, Any]:
        span = trace_context.begin_span(
            "evidence_aggregation",
            input_payload={
                "structured_count": len(structured_evidence),
                "document_count": len(document_evidence),
                "sources": sources,
            },
            metadata={"service": "EvidenceAggregatorService"},
        ) if trace_context else None

        merged_sources: list[str] = []
        for source in sources:
            if source not in merged_sources:
                merged_sources.append(source)

        aggregated = {
            "structured_evidence": structured_evidence,
            "document_evidence": [dict(document) for document in document_evidence],
            "sources": merged_sources,
        }
        if span:
            span.finish(
                output={
                    "structured_count": len(structured_evidence),
                    "document_count": len(document_evidence),
                    "source_count": len(merged_sources),
                },
                metadata={
                    "structured_count": len(structured_evidence),
                    "document_count": len(document_evidence),
                    "source_count": len(merged_sources),
                },
            )
        return aggregated
