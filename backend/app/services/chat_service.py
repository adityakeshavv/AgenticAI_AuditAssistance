"""
ChatService
===========
Orchestrates a full conversational turn:
  1. Load / create session memory
  2. Resolve follow-up references via ConversationContextManager
  3. Inject memory context into the investigation planner
  4. Run the existing AgentService pipeline
  5. Generate suggested next actions
  6. Persist the turn to memory
  7. Return the enriched chat response
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.agent_service import AgentService
from app.services.conversation_memory_service import ConversationMemoryService
from app.services.conversation_context_manager import ConversationContextManager
from app.services.suggested_actions_service import SuggestedActionsService

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.context_manager = ConversationContextManager()
        self.suggested_actions_service = SuggestedActionsService()

    def chat(
        self,
        *,
        message: str,
        session_id: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> dict[str, Any]:
        # 1. Get / create session
        session_id, _session = ConversationMemoryService.get_or_create(session_id)

        # 2. Resolve follow-up references
        ctx = self.context_manager.resolve(message, session_id)
        resolved_query = ctx["resolved_query"]
        is_followup = ctx["is_followup"]
        memory_context = ctx["memory_context"]

        logger.info(
            "Chat turn: session=%s followup=%s resolved=%r",
            session_id[:8], is_followup, resolved_query,
        )

        # 3. Run audit agent pipeline (with context injected into planner)
        agent_svc = AgentService(self.db)
        # Patch the planner so it receives conversation context
        _original_plan = agent_svc.investigation_planner.plan

        def _plan_with_context(query: str, **kwargs: Any) -> dict[str, Any]:
            existing_ctx = kwargs.get("investigation_context") or {}
            existing_ctx["conversation_context"] = memory_context
            kwargs["investigation_context"] = existing_ctx
            return _original_plan(query, **kwargs)

        agent_svc.investigation_planner.plan = _plan_with_context  # type: ignore[method-assign]

        audit_response = agent_svc.run(
            query=resolved_query,
            page=page,
            page_size=page_size,
        )

        # 4. Generate suggested actions
        suggested_actions = self.suggested_actions_service.suggest(
            query=resolved_query,
            response_contract=audit_response,
            memory_context=memory_context,
        )

        # 5. Persist turn
        ConversationMemoryService.add_turn(
            session_id,
            user_message=message,
            assistant_response=audit_response,
        )

        # 6. Build investigation state for frontend
        investigation_state = ConversationMemoryService.get_investigation_state(session_id)
        # Convert sets to lists for JSON serialisation
        investigation_state["entity_ids"] = list(investigation_state.get("entity_ids", set()))
        investigation_state["transaction_ids"] = list(investigation_state.get("transaction_ids", set()))

        # 7. Return enriched response
        return {
            **audit_response,
            # Conversation metadata
            "session_id": session_id,
            "is_followup": is_followup,
            "resolved_query": resolved_query,
            "original_query": message,
            "injected_context": ctx.get("injected_context", {}),
            # Suggested next actions
            "suggested_actions": suggested_actions,
            # Live investigation state
            "investigation_state": investigation_state,
            # Conversation history summary
            "turn_count": len(ConversationMemoryService.get_session(session_id)["session"]["turns"]),
        }
