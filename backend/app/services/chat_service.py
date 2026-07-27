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
from app.services.chat_session_service import ChatSessionService
from app.services.database_connector_service import DatabaseConnectorService
from app.services.document_metadata_service import DocumentMetadataService
from app.services.conversation_memory_service import ConversationMemoryService
from app.services.conversation_context_manager import ConversationContextManager
from app.services.conversation_mode_service import ConversationModeService
from app.services.governance_audit_service import GovernanceAuditService
from app.services.suggested_actions_service import SuggestedActionsService

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.context_manager = ConversationContextManager()
        self.session_service = ChatSessionService(db)
        self.conversation_mode_service = ConversationModeService()
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
        attached_document_ids: list[str] | None = None,
        user_name: str | None = None,
    ) -> dict[str, Any]:
        # 1. Get / create persistent session and hydrate in-memory context
        session_id = self.session_service.ensure_session(
            session_id=session_id,
            user_id=user_id or "anonymous",
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        attached_document_ids = [doc_id for doc_id in (attached_document_ids or []) if doc_id]
        attached_documents = []
        if attached_document_ids:
            document_service = DocumentMetadataService(self.db)
            for document_id in attached_document_ids:
                document = document_service.get_document_by_id(document_id)
                if document:
                    attached_documents.append(document)

        # 2. Resolve follow-up references
        ctx = self.context_manager.resolve(message, session_id)
        resolved_query = ctx["resolved_query"]
        is_followup = ctx["is_followup"]
        memory_context = ctx["memory_context"]

        if attached_documents:
            memory_context = {
                **memory_context,
                "attached_document_ids": attached_document_ids,
                "attached_documents": attached_documents,
            }
            ctx["injected_context"] = {
                **ctx.get("injected_context", {}),
                "attached_document_ids": attached_document_ids,
                "attached_documents": attached_documents,
            }

        conversation = self.conversation_mode_service.classify(
            resolved_query,
            user_name=user_name,
            memory_context=memory_context,
        )

        logger.info(
            "Chat turn: session=%s followup=%s mode=%s resolved=%r",
            session_id[:8], is_followup, conversation.mode, resolved_query,
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
                "attached_document_ids": attached_document_ids,
                "conversation_mode": conversation.mode,
            },
        )
        self.db.commit()

        if not conversation.should_route_audit:
            assistant_message = conversation.assistant_message
            if not assistant_message:
                assistant_message = "I'm here whenever you want to continue with an audit question."

            response_payload = self._build_conversation_response(
                query=message,
                resolved_query=resolved_query,
                session_id=session_id,
                assistant_message=assistant_message,
                conversation_mode=conversation.mode,
                is_followup=is_followup,
                user_name=user_name,
            )
            self.session_service.record_turn(
                session_id=session_id,
                user_id=user_id or "anonymous",
                user_message=message,
                assistant_message=assistant_message,
                assistant_mode=conversation.mode,
                is_followup=is_followup,
                resolved_query=resolved_query,
                response_payload=response_payload,
            )
            session = self._get_session_summary(session_id, user_id)
            GovernanceAuditService(self.db).record_event(
                actor_user_id=user_id,
                action_type="chat_turn_completed",
                entity_type="chat_session",
                entity_id=session_id,
                severity="info",
                summary=f"Chat turn completed for session {session_id[:8]}.",
                after_state={
                    "turn_count": session.get("turn_count", 1),
                    "conversation_mode": conversation.mode,
                    "finding_title": response_payload.get("finding", {}).get("title"),
                },
            )
            self.db.commit()
            return response_payload

        # 3. Run audit agent pipeline (with context injected into planner)
        connector = DatabaseConnectorService(self.db)
        with connector.open_session(
            user_id=user_id or "anonymous",
            connection_id=connection_id,
            workspace_id=workspace_id,
        ) as data_db:
            agent_svc = AgentService(data_db, audit_db=self.db)
            # Patch the planner so it receives conversation context
            _original_plan = agent_svc.workflow.investigation_planner.plan

            def _plan_with_context(query: str, **kwargs: Any) -> dict[str, Any]:
                existing_ctx = kwargs.get("investigation_context") or {}
                existing_ctx["conversation_context"] = memory_context
                kwargs["investigation_context"] = existing_ctx
                return _original_plan(query, **kwargs)

            agent_svc.workflow.investigation_planner.plan = _plan_with_context  # type: ignore[method-assign]

            try:
                audit_response = agent_svc.run(
                    query=resolved_query,
                    page=page,
                    page_size=page_size,
                    actor_user_id=user_id,
                    attached_document_ids=attached_document_ids,
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

            audit_response = {
                **audit_response,
                "assistant_message": audit_response.get("assistant_message") or audit_response.get("final_response") or "",
                "conversation_mode": "audit",
            }

            # 5. Persist turn
            self.session_service.record_turn(
                session_id=session_id,
                user_id=user_id or "anonymous",
                user_message=message,
                assistant_message=str(audit_response.get("assistant_message") or audit_response.get("final_response") or ""),
                assistant_mode="audit",
                is_followup=is_followup,
                resolved_query=resolved_query,
                response_payload=audit_response,
            )
            session = self._get_session_summary(session_id, user_id)
            audit_response["session_title"] = session.get("session_title", "New chat")

            # 6. Build investigation state for frontend
            ConversationMemoryService.add_turn(
                session_id,
                user_message=message,
                assistant_response=audit_response,
            )
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
                    "turn_count": self._get_session_summary(session_id, user_id).get("turn_count", 1),
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
                "turn_count": self._get_session_summary(session_id, user_id).get("turn_count", 1),
            }

    def _get_session_summary(self, session_id: str, user_id: str | None) -> dict[str, Any]:
        if not user_id:
            return {}
        session = self.session_service.get_history(session_id=session_id, user_id=user_id)
        return session

    @staticmethod
    def _build_conversation_response(
        *,
        query: str,
        resolved_query: str,
        session_id: str,
        assistant_message: str,
        conversation_mode: str,
        is_followup: bool,
        user_name: str | None,
    ) -> dict[str, Any]:
        first_name = (user_name or "").strip().split(" ")[0] if user_name else ""
        return {
            "success": True,
            "query": query,
            "intent": {"type": "conversation", "mode": conversation_mode},
            "investigation_plan": {},
            "entities_investigated": [],
            "entity_type": None,
            "entity_id": None,
            "agents_used": [],
            "risk_rating": "N/A",
            "risk_score": 0,
            "risk_drivers": [],
            "document_intelligence_summary": "",
            "document_intelligence": {},
            "investigation_summary": assistant_message,
            "investigation_metrics": {
                "transactions_reviewed": 0,
                "contracts_reviewed": 0,
                "documents_reviewed": 0,
                "flagged_transactions": 0,
            },
            "top_supporting_evidence": [],
            "transaction_summary": "",
            "vendor_summary": "",
            "key_findings": [],
            "supporting_evidence": [],
            "supporting_documents": [],
            "citations": [],
            "navigation_payloads": [],
            "recommendations": [],
            "structured_evidence": [],
            "document_evidence": [],
            "sources": [],
            "reasoning": [assistant_message],
            "finding": {
                "title": "Conversation",
                "summary": assistant_message,
                "category": "Conversation",
                "severity": "Info",
                "recommendation": "",
            },
            "final_response": assistant_message,
            "traceability": {
                "agents_invoked": [],
                "agent_selection_reasoning": [],
                "sources_used": [],
                "evidence_used": [],
                "reasoning_path": [assistant_message],
                "execution_metadata": [],
                "langfuse": {"enabled": False, "trace_id": None, "trace_url": None, "session_id": session_id},
            },
            "evaluation": {
                "retrieval_relevance": "Not Applicable",
                "grounding_quality": "Not Applicable",
                "faithfulness": "Not Applicable",
                "citation_coverage": "Not Applicable",
                "summary": "This was handled as a conversational response rather than an audit investigation.",
            },
            "execution_metadata": [],
            "message": assistant_message,
            "session_id": session_id,
            "session_title": session_id,
            "is_followup": is_followup,
            "resolved_query": resolved_query,
            "original_query": query,
            "assistant_message": assistant_message,
            "conversation_mode": conversation_mode,
            "injected_context": {},
            "suggested_actions": [],
            "investigation_state": {
                "entity_type": None,
                "entity_ids": [],
                "transaction_ids": [],
                "topics": [],
                "risk_rating": None,
                "transaction_count": 0,
                "document_count": 0,
                "finding_count": 0,
                "key_findings": [],
                "recommendations": [],
                "status": "idle",
            },
            "turn_count": 1,
        }
