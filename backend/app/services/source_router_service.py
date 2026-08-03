from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import get_settings
from app.prompts.source_router_prompt import build_source_router_messages
from app.services.gemini_client_service import GeminiClientService


logger = logging.getLogger(__name__)


class SourceRouterService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.gemini_client = GeminiClientService()

    def route(
        self,
        query: str,
        *,
        attached_document_ids: list[str] | None = None,
        memory_context: dict[str, Any] | None = None,
        trace_context: Any | None = None,
    ) -> dict[str, Any]:
        attached_document_ids = [doc_id for doc_id in (attached_document_ids or []) if doc_id]
        normalized = self._normalize(query)
        route_span = trace_context.begin_span(
            "source_routing",
            input_payload={
                "query": query,
                "attached_document_ids": attached_document_ids,
                "memory_context": memory_context or {},
            },
            metadata={"service": "SourceRouterService"},
        ) if trace_context else None

        if self.settings.agent_runtime == "gemini_adk" and self.gemini_client.is_configured():
            try:
                response_text = self.gemini_client.generate_json(
                    system_prompt=self._system_prompt(),
                    user_prompt=json.dumps(
                        {
                            "query": query,
                            "attached_document_ids": attached_document_ids,
                            "memory_context": memory_context or {},
                        },
                        indent=2,
                        default=str,
                    ),
                    model=self.settings.gemini_model,
                )
                parsed = self._parse_response(response_text)
                if route_span:
                    route_span.finish(output=parsed, metadata={"service": "SourceRouterService", "model": self.settings.gemini_model})
                return parsed
            except Exception as exc:
                logger.warning("Gemini source routing failed, using heuristic fallback: %s", exc)

        if self.settings.openai_api_key:
            try:
                from openai import OpenAI
            except ImportError as exc:
                logger.warning("openai package unavailable for source routing: %s", exc)
            else:
                try:
                    client = OpenAI(api_key=self.settings.openai_api_key)
                    response = client.chat.completions.create(
                        model=self.settings.openai_model,
                        temperature=0,
                        messages=build_source_router_messages(
                            query=query,
                            attached_document_ids=attached_document_ids,
                            memory_context=memory_context or {},
                        ),
                    )
                    content = response.choices[0].message.content or ""
                    parsed = self._parse_response(content)
                    if route_span:
                        route_span.finish(output=parsed, metadata={"service": "SourceRouterService", "model": self.settings.openai_model})
                    return parsed
                except Exception as exc:
                    logger.warning("LLM source routing failed, using heuristic fallback: %s", exc)

        fallback = self._heuristic_route(normalized, attached_document_ids=attached_document_ids, memory_context=memory_context or {})
        if route_span:
            route_span.finish(output=fallback, metadata={"service": "SourceRouterService", "runtime": "heuristic"})
        return fallback

    def _system_prompt(self) -> str:
        return (
            "You route audit questions to the most likely evidence source. Return JSON only."
        )

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise ValueError("Source router response must be a JSON object.")

        source_mode = str(payload.get("source_mode") or "unknown").strip().lower()
        confidence = float(payload.get("confidence", 0.0) or 0.0)
        reason = str(payload.get("reason") or "").strip()
        candidate_sources = payload.get("candidate_sources")
        use_pdf = bool(payload.get("use_pdf", False))
        use_database = bool(payload.get("use_database", False))

        if source_mode not in {"pdf_only", "db_only", "both", "unknown"}:
            raise ValueError(f"Invalid source mode returned by LLM: {source_mode}")
        if candidate_sources is None:
            candidate_sources = self._candidate_sources(source_mode)
        if not isinstance(candidate_sources, list):
            raise ValueError("candidate_sources must be a list.")

        if source_mode == "pdf_only":
            use_pdf = True
            use_database = False
        elif source_mode == "db_only":
            use_pdf = False
            use_database = True
        elif source_mode == "both":
            use_pdf = True
            use_database = True
        else:
            use_pdf = bool(use_pdf)
            use_database = bool(use_database)

        if not reason:
            reason = self._default_reason(source_mode)

        return {
            "source_mode": source_mode,
            "confidence": max(0.0, min(confidence, 1.0)),
            "reason": reason,
            "candidate_sources": candidate_sources,
            "use_pdf": use_pdf,
            "use_database": use_database,
            "decision_source": "llm",
        }

    def _heuristic_route(
        self,
        normalized: str,
        *,
        attached_document_ids: list[str],
        memory_context: dict[str, Any],
    ) -> dict[str, Any]:
        document_signals = (
            "pdf",
            "document",
            "documents",
            "file",
            "files",
            "contract",
            "policy",
            "policies",
            "email",
            "e-mail",
            "report",
            "attachment",
            "attachments",
            "uploaded",
        )
        db_signals = (
            "transaction",
            "transactions",
            "vendor",
            "vendors",
            "approval",
            "approvals",
            "compliance",
            "threshold",
            "risk",
            "expense",
            "claim",
        )
        has_document_signal = any(signal in normalized for signal in document_signals) or bool(attached_document_ids)
        has_db_signal = any(signal in normalized for signal in db_signals)
        has_both_signal = has_document_signal and has_db_signal
        recent_docs = memory_context.get("attached_document_ids") or []
        if recent_docs:
            has_document_signal = True

        if has_both_signal:
            source_mode = "both"
        elif has_document_signal and not has_db_signal:
            source_mode = "pdf_only"
        elif has_db_signal and not has_document_signal:
            source_mode = "db_only"
        elif has_document_signal and has_db_signal:
            source_mode = "both"
        else:
            source_mode = "db_only"

        confidence = 0.88 if source_mode != "both" else 0.82
        return {
            "source_mode": source_mode,
            "confidence": confidence,
            "reason": self._default_reason(source_mode),
            "candidate_sources": self._candidate_sources(source_mode),
            "use_pdf": source_mode in {"pdf_only", "both"},
            "use_database": source_mode in {"db_only", "both"},
            "decision_source": "heuristic",
        }

    def _candidate_sources(self, source_mode: str) -> list[str]:
        if source_mode == "pdf_only":
            return ["pdf"]
        if source_mode == "db_only":
            return ["database"]
        if source_mode == "both":
            return ["pdf", "database"]
        return ["database"]

    def _default_reason(self, source_mode: str) -> str:
        if source_mode == "pdf_only":
            return "The query appears to rely primarily on uploaded documents and source text."
        if source_mode == "db_only":
            return "The query appears to rely primarily on structured database records."
        if source_mode == "both":
            return "The query spans uploaded documents and structured records, so both sources should be consulted."
        return "The query did not clearly map to a single source, so the structured database is the safest default."

    @staticmethod
    def _normalize(query: str) -> str:
        return " ".join(query.lower().strip().split())
