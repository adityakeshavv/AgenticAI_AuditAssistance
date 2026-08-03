"""
ConversationContextManager
==========================
Resolves follow-up references by asking the model whether the new message
depends on prior conversation context, then rewrites it into a self-contained
query when needed.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings
from app.prompts.conversation_context_prompt import build_conversation_context_messages
from app.services.conversation_memory_service import ConversationMemoryService
from app.services.conversation_memory_search_service import ConversationMemorySearchService

logger = logging.getLogger(__name__)


class ConversationContextManager:
    """Enriches an incoming query with conversation context."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def resolve(
        self,
        query: str,
        session_id: str,
    ) -> dict[str, Any]:
        """
        Returns a context bundle:
          - resolved_query   : query with references resolved (may equal original)
          - is_followup      : bool
          - injected_context : dict of what was injected
          - planner_context  : full context for the investigation planner
          - memory_context   : conversation memory snapshot
        """
        session_ctx = ConversationMemoryService.get_context_for_planner(session_id)
        memory_search_service = ConversationMemorySearchService()
        memory_search = memory_search_service.search(
            query=query,
            session_id=session_id,
            top_k=5,
            memory_context=session_ctx,
        )
        resolved_query = query
        injected: dict[str, Any] = {}
        is_followup = False

        if session_ctx.get("recent_turns") and self.settings.openai_api_key:
            try:
                is_followup, resolved_query, injected = self._llm_resolve(query, session_ctx)
            except Exception as exc:
                logger.warning("LLM follow-up resolution failed, falling back to original query: %s", exc)

        if not is_followup and not resolved_query:
            resolved_query = query

        enriched_memory_context = {
            **session_ctx,
            "memory_evidence": memory_search.get("memory_evidence", []),
            "memory_sources": memory_search.get("memory_sources", []),
            "memory_summary": memory_search.get("memory_summary", ""),
            "memory_matches": memory_search.get("memory_matches", 0),
        }

        return {
            "resolved_query": resolved_query,
            "original_query": query,
            "is_followup": is_followup,
            "injected_context": injected,
            "planner_context": session_ctx,
            "memory_context": enriched_memory_context,
        }

    def _llm_resolve(
        self,
        query: str,
        ctx: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        from openai import OpenAI

        client = OpenAI(api_key=self.settings.openai_api_key)

        response = client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0,
            messages=build_conversation_context_messages(
                query=query,
                session_context=ctx,
            ),
        )
        content = (response.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        parsed = json.loads(content)
        is_followup = bool(parsed.get("is_followup", False))
        resolved_query = str(parsed.get("resolved_query", query)).strip() or query
        injected = parsed.get("injected_context", {})
        if not isinstance(injected, dict):
            injected = {}
        return is_followup, resolved_query, dict(injected)
