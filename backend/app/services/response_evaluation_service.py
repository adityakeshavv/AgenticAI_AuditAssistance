from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings
from app.prompts.response_evaluation_prompt import build_response_evaluation_messages


logger = logging.getLogger(__name__)


class ResponseEvaluationService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def evaluate(
        self,
        *,
        query: str,
        response_contract: dict[str, Any],
        trace_context: Any | None = None,
    ) -> dict[str, Any]:
        return self._evaluate(query=query, response_contract=response_contract, trace_context=trace_context)

    def _evaluate(
        self,
        *,
        query: str,
        response_contract: dict[str, Any],
        trace_context: Any | None = None,
    ) -> dict[str, Any]:
        structured_evidence = list(response_contract.get("structured_evidence", []))
        document_evidence = list(response_contract.get("document_evidence", []))
        citations = list(response_contract.get("citations", []))
        final_response = str(response_contract.get("final_response") or "")

        if not self.settings.openai_api_key:
            evaluation = self._deterministic_evaluation(
                query=query,
                final_response=final_response,
                structured_evidence=structured_evidence,
                document_evidence=document_evidence,
                citations=citations,
            )
            if trace_context:
                trace_context.log_generation(
                    "response_evaluation",
                    model="deterministic",
                    input_payload={
                        "query": query,
                        "final_response": final_response,
                        "structured_evidence_count": len(structured_evidence),
                        "document_evidence_count": len(document_evidence),
                        "citation_count": len(citations),
                    },
                    output_payload=evaluation,
                    metadata={"service": "ResponseEvaluationService", "mode": "deterministic"},
                )
            return evaluation

        try:
            from openai import OpenAI
        except ImportError:
            evaluation = self._deterministic_evaluation(
                query=query,
                final_response=final_response,
                structured_evidence=structured_evidence,
                document_evidence=document_evidence,
                citations=citations,
            )
            if trace_context:
                trace_context.log_generation(
                    "response_evaluation",
                    model="deterministic",
                    input_payload={
                        "query": query,
                        "final_response": final_response,
                        "structured_evidence_count": len(structured_evidence),
                        "document_evidence_count": len(document_evidence),
                        "citation_count": len(citations),
                    },
                    output_payload=evaluation,
                    metadata={"service": "ResponseEvaluationService", "mode": "deterministic"},
                )
            return evaluation

        try:
            client = OpenAI(api_key=self.settings.openai_api_key)
            llm_span = trace_context.begin_span(
                "response_evaluation",
                input_payload={
                    "query": query,
                    "final_response": final_response,
                    "structured_evidence": structured_evidence,
                    "document_evidence": document_evidence,
                    "citations": citations,
                },
                metadata={"service": "ResponseEvaluationService", "model": self.settings.openai_model},
            ) if trace_context else None
            response = client.chat.completions.create(
                model=self.settings.openai_model,
                temperature=0,
                messages=build_response_evaluation_messages(
                    query=query,
                    final_response=final_response,
                    structured_evidence=structured_evidence,
                    document_evidence=document_evidence,
                    citations=citations,
                ),
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("LLM returned an empty response evaluation.")
            parsed = self._parse_response(content)
            if parsed:
                usage = getattr(response, "usage", None)
                usage_payload = {}
                if usage is not None:
                    usage_payload = {
                        "prompt_tokens": getattr(usage, "prompt_tokens", None),
                        "completion_tokens": getattr(usage, "completion_tokens", None),
                        "total_tokens": getattr(usage, "total_tokens", None),
                    }
                if llm_span:
                    llm_span.finish(
                        output=parsed,
                        metadata={"service": "ResponseEvaluationService", "usage": usage_payload, "model": self.settings.openai_model},
                    )
                return parsed
        except Exception as exc:
            logger.warning("LLM response evaluation failed. Falling back to deterministic evaluation: %s", exc)

        evaluation = self._deterministic_evaluation(
            query=query,
            final_response=final_response,
            structured_evidence=structured_evidence,
            document_evidence=document_evidence,
            citations=citations,
        )
        if trace_context:
            trace_context.log_generation(
                "response_evaluation",
                model="deterministic",
                input_payload={
                    "query": query,
                    "final_response": final_response,
                    "structured_evidence_count": len(structured_evidence),
                    "document_evidence_count": len(document_evidence),
                    "citation_count": len(citations),
                },
                output_payload=evaluation,
                metadata={"service": "ResponseEvaluationService", "mode": "deterministic"},
            )
        return evaluation

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise ValueError("Response evaluation must be a JSON object.")

        return {
            "retrieval_relevance": self._normalize_choice(payload.get("retrieval_relevance"), {"high", "medium", "low"}, "Medium"),
            "grounding_quality": self._normalize_choice(payload.get("grounding_quality"), {"strong", "adequate", "weak"}, "Adequate"),
            "faithfulness": self._normalize_choice(payload.get("faithfulness"), {"high", "medium", "low"}, "Medium"),
            "citation_coverage": self._normalize_choice(payload.get("citation_coverage"), {"complete", "partial", "minimal"}, "Partial"),
            "summary": str(payload.get("summary") or "").strip() or "The response was evaluated for grounding and citation coverage.",
        }

    def _deterministic_evaluation(
        self,
        *,
        query: str,
        final_response: str,
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
        citations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        structured_count = len(structured_evidence)
        document_count = len(document_evidence)
        citation_count = len(citations)

        retrieval_relevance = "High" if final_response.strip() else "Low"
        if structured_count == 0 and document_count == 0:
            retrieval_relevance = "Low"

        grounding_quality = "Strong" if (structured_count + document_count) >= 4 and citation_count >= 1 else "Adequate"
        if structured_count == 0 and document_count == 0:
            grounding_quality = "Weak"
        elif citation_count == 0:
            grounding_quality = "Adequate" if structured_count + document_count else "Weak"

        faithfulness = "High" if structured_count > 0 and final_response.strip() else "Medium"
        if structured_count == 0 and document_count == 0:
            faithfulness = "Low"

        if citation_count >= max(1, document_count):
            citation_coverage = "Complete" if document_count > 0 else "Partial"
        elif citation_count > 0:
            citation_coverage = "Partial"
        else:
            citation_coverage = "Minimal"

        summary = (
            f"Deterministic evaluation based on {structured_count} structured record(s), "
            f"{document_count} document evidence item(s), and {citation_count} citation(s). "
            f"The response appears {'supported' if structured_count or document_count else 'lightly supported'} by the retrieved evidence."
        )
        if not final_response.strip():
            summary += " The final response was empty or minimal."
        return {
            "retrieval_relevance": retrieval_relevance,
            "grounding_quality": grounding_quality,
            "faithfulness": faithfulness,
            "citation_coverage": citation_coverage,
            "summary": summary,
        }

    def _normalize_choice(self, value: Any, allowed: set[str], fallback: str) -> str:
        candidate = str(value or "").strip()
        if not candidate:
            return fallback
        normalized = candidate.lower()
        if normalized not in allowed:
            return fallback
        return candidate[:1].upper() + candidate[1:].lower()
