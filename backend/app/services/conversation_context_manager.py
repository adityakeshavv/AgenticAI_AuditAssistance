"""
ConversationContextManager
==========================
Resolves follow-up references ("these", "that vendor", "the same transaction")
by injecting context from the conversation memory into the current query before
the planner and agents receive it.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings
from app.services.conversation_memory_service import ConversationMemoryService

logger = logging.getLogger(__name__)

_REFERENCE_WORDS = {
    "these", "those", "that", "it", "them", "this",
    "the same", "the flagged", "the vendor", "the transaction",
    "previously", "the ones", "the results", "the findings",
}


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
        is_followup = self._detect_followup(query, session_ctx)
        resolved_query = query

        injected: dict[str, Any] = {}

        if is_followup and session_ctx.get("recent_turns"):
            if self.settings.openai_api_key:
                try:
                    resolved_query, injected = self._llm_resolve(query, session_ctx)
                except Exception as exc:
                    logger.warning("LLM follow-up resolution failed, using heuristic: %s", exc)
                    resolved_query, injected = self._heuristic_resolve(query, session_ctx)
            else:
                resolved_query, injected = self._heuristic_resolve(query, session_ctx)

        return {
            "resolved_query": resolved_query,
            "original_query": query,
            "is_followup": is_followup,
            "injected_context": injected,
            "planner_context": session_ctx,
            "memory_context": session_ctx,
        }

    # ── Detection ──────────────────────────────────────────────────────────

    @staticmethod
    def _detect_followup(query: str, ctx: dict[str, Any]) -> bool:
        if not ctx.get("recent_turns"):
            return False
        q = query.lower().strip()
        for ref in _REFERENCE_WORDS:
            if ref in q:
                return True
        # Short queries with no entity IDs are usually follow-ups
        if len(q.split()) <= 6 and not any(
            kw in q for kw in ("vendor", "transaction", "investigate", "show", "list", "find")
        ):
            return True
        return False

    # ── LLM resolution ─────────────────────────────────────────────────────

    def _llm_resolve(
        self,
        query: str,
        ctx: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        from openai import OpenAI

        client = OpenAI(api_key=self.settings.openai_api_key)

        recent = ctx.get("recent_turns", [])[-4:]
        inv = ctx.get("active_investigation", {})

        history_text = "\n".join(
            f"User: {t['user']}\nAssistant: {t['summary']}" for t in recent
        )

        system = (
            "You are a context resolver for an enterprise audit assistant.\n"
            "Given the conversation history and the current user message, "
            "rewrite the message so it is fully self-contained (all pronouns and "
            "references replaced with explicit entities).\n"
            "If the message is already self-contained, return it unchanged.\n"
            "Also extract what context was injected.\n"
            "Return JSON only:\n"
            '{"resolved_query": "...", "injected": {"entity_type": "...", "entity_ids": [...], "topic": "..."}}'
        )
        user_msg = (
            f"Conversation history:\n{history_text}\n\n"
            f"Active investigation: entity_type={inv.get('entity_type')}, "
            f"entity_ids={list(inv.get('entity_ids', []))[:5]}, "
            f"topics={inv.get('topics', [])}\n\n"
            f"Current message: {query}"
        )

        resp = client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        )
        content = (resp.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        parsed = json.loads(content)
        return str(parsed.get("resolved_query", query)), dict(parsed.get("injected", {}))

    # ── Heuristic resolution ────────────────────────────────────────────────

    @staticmethod
    def _heuristic_resolve(
        query: str,
        ctx: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        inv = ctx.get("active_investigation", {})
        recent = ctx.get("recent_turns", [])

        injected: dict[str, Any] = {}
        resolved = query

        entity_ids = list(inv.get("entity_ids", []))
        tx_ids = list(inv.get("transaction_ids", []))
        entity_type = inv.get("entity_type")

        q_lower = query.lower()

        # Inject last known vendor ID if query references "vendor" without an ID
        if "vendor" in q_lower and not any(c.isdigit() for c in query):
            vendor_ids = [eid for eid in entity_ids if "VND" in eid or "vendor" in eid.lower()]
            if vendor_ids:
                resolved = f"{query} (referring to vendor {vendor_ids[0]})"
                injected["vendor_id"] = vendor_ids[0]

        # Inject last known transaction IDs for "these" / "those"
        if any(ref in q_lower for ref in ("these", "those", "them", "the flagged")):
            if tx_ids:
                ids_text = ", ".join(tx_ids[:5])
                resolved = f"{query} (referring to transactions: {ids_text})"
                injected["transaction_ids"] = tx_ids[:5]

        # Inject most recent finding context
        if any(ref in q_lower for ref in ("why", "explain", "reason", "cause")):
            if recent:
                last = recent[-1]
                resolved = f"{query} (in context of: {last['summary'][:200]})"
                injected["prior_summary"] = last["summary"][:200]

        injected["entity_type"] = entity_type
        return resolved, injected
