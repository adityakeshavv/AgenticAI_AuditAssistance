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
from app.services.database_connector_service import DatabaseConnectorService
from app.services.conversation_memory_service import ConversationMemoryService
from app.services.conversation_context_manager import ConversationContextManager
from app.services.governance_audit_service import GovernanceAuditService
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
        user_id: str | None = None,
        connection_id: str | None = None,
        workspace_id: str | None = None,
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
        GovernanceAuditService(self.db).record_event(
            actor_user_id=user_id,
            action_type="chat_turn_started",
            entity_type="chat_session",
            entity_id=session_id,
            severity="info",
            summary=f"Chat turn started for session {session_id[:8]}.",
            after_state={
                "original_message": message,
                "resolved_query": resolved_query,
                "is_followup": is_followup,
                "workspace_id": workspace_id,
                "connection_id": connection_id,
            },
        )
        self.db.commit()

        # 3. Run audit agent pipeline (with context injected into planner)
        connector = DatabaseConnectorService(self.db)
        with connector.open_session(
            user_id=user_id or "anonymous",
            connection_id=connection_id,
            workspace_id=workspace_id,
        ) as data_db:
            agent_svc = AgentService(data_db, audit_db=self.db)
            # Patch the planner so it receives conversation context
            _original_plan = agent_svc.investigation_planner.plan

            def _plan_with_context(query: str, **kwargs: Any) -> dict[str, Any]:
                existing_ctx = kwargs.get("investigation_context") or {}
                existing_ctx["conversation_context"] = memory_context
                kwargs["investigation_context"] = existing_ctx
                return _original_plan(query, **kwargs)

            agent_svc.investigation_planner.plan = _plan_with_context  # type: ignore[method-assign]

            try:
                audit_response = agent_svc.run(
                    query=resolved_query,
                    page=page,
                    page_size=page_size,
                    actor_user_id=user_id,
                )
            except Exception as exc:
                GovernanceAuditService(self.db).record_event(
                    actor_user_id=user_id,
                    action_type="chat_turn_failed",
                    entity_type="chat_session",
                    entity_id=session_id,
                    severity="warning",
                    summary=f"Chat turn failed for session {session_id[:8]}.",
                    after_state={"error": str(exc), "resolved_query": resolved_query},
                )
                self.db.commit()
                raise

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
            GovernanceAuditService(self.db).record_event(
                actor_user_id=user_id,
                action_type="chat_turn_completed",
                entity_type="chat_session",
                entity_id=session_id,
                severity="info",
                summary=f"Chat turn completed for session {session_id[:8]}.",
                after_state={
                    "turn_count": len(ConversationMemoryService.get_session(session_id)["session"]["turns"]) + 1,
                    "risk_rating": audit_response.get("risk_rating"),
                    "finding_title": audit_response.get("finding", {}).get("title"),
                },
            )
            self.db.commit()
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
