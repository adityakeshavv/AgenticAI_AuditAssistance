from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import chat_crud
from app.services.conversation_memory_service import ConversationMemoryService


class ChatSessionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_session(
        self,
        *,
        user_id: str,
        workspace_id: str | None = None,
        connection_id: str | None = None,
    ) -> dict[str, Any]:
        session = chat_crud.create_session(
            self.db,
            user_id=user_id,
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        self.db.commit()
        self.db.refresh(session)
        ConversationMemoryService.get_or_create(session.session_id)
        return self._serialize_session_summary(session)

    def ensure_session(
        self,
        *,
        session_id: str | None,
        user_id: str,
        workspace_id: str | None = None,
        connection_id: str | None = None,
    ) -> str:
        if session_id:
            session = chat_crud.get_session_for_user(self.db, session_id, user_id)
            if session:
                if session_id not in ConversationMemoryService.list_sessions():
                    self._hydrate_memory(session_id)
                return session.session_id

        session = chat_crud.create_session(
            self.db,
            user_id=user_id,
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        self.db.commit()
        self.db.refresh(session)
        ConversationMemoryService.get_or_create(session.session_id)
        return session.session_id

    def list_sessions(self, *, user_id: str) -> list[dict[str, Any]]:
        sessions = chat_crud.list_sessions_for_user(self.db, user_id)
        return [self._serialize_session_summary(session) for session in sessions]

    def get_history(self, *, session_id: str, user_id: str) -> dict[str, Any]:
        session = self._require_session(session_id=session_id, user_id=user_id)
        turns = chat_crud.list_turns(self.db, session.session_id)
        return {
            "session_id": session.session_id,
            "session_title": session.session_title,
            "turn_count": session.turn_count,
            "workspace_id": session.workspace_id,
            "connection_id": session.connection_id,
            "created_at": self._format_dt(session.created_at),
            "updated_at": self._format_dt(session.updated_at),
            "last_message_at": self._format_dt(session.last_message_at),
            "turns": [self._serialize_turn(turn) for turn in turns],
        }

    def record_turn(
        self,
        *,
        session_id: str,
        user_id: str,
        user_message: str,
        assistant_message: str,
        assistant_mode: str,
        is_followup: bool,
        resolved_query: str,
        response_payload: dict[str, Any],
    ) -> dict[str, Any]:
        session = self._require_session(session_id=session_id, user_id=user_id)
        response_payload = self._normalize_response_payload(response_payload, session.session_id)
        turn = chat_crud.append_turn(
            self.db,
            session,
            user_message=user_message,
            assistant_message=assistant_message,
            assistant_mode=assistant_mode,
            is_followup=is_followup,
            resolved_query=resolved_query,
            response_payload=response_payload,
        )
        self.db.commit()
        self.db.refresh(session)
        self.db.refresh(turn)
        return self._serialize_turn(turn)

    def archive_session(self, *, session_id: str, user_id: str) -> dict[str, Any]:
        session = self._require_session(session_id=session_id, user_id=user_id)
        chat_crud.archive_session(self.db, session)
        self.db.commit()
        return {"cleared": True, "session_id": session_id}

    def _hydrate_memory(self, session_id: str) -> None:
        turns = chat_crud.list_turns(self.db, session_id)
        memory_turns = []
        for turn in turns:
            response = dict(turn.response_payload or {})
            memory_turns.append(
                {
                    "turn_id": turn.turn_id,
                    "timestamp": turn.created_at.isoformat() if turn.created_at else "",
                    "user": turn.user_message,
                    "assistant_summary": turn.assistant_message,
                    "risk_rating": response.get("risk_rating"),
                    "key_findings": list(response.get("key_findings", [])),
                    "entities_investigated": list(response.get("entities_investigated", [])),
                    "entity_type": response.get("entity_type"),
                    "entity_id": response.get("entity_id"),
                    "structured_evidence_count": len(response.get("structured_evidence", [])),
                    "document_evidence_count": len(response.get("document_evidence", [])),
                    "citations_count": len(response.get("citations", [])),
                    "agents_used": list(response.get("agents_used", [])),
                    "transaction_summary": response.get("transaction_summary", ""),
                    "vendor_summary": response.get("vendor_summary", ""),
                    "investigation_summary": response.get("investigation_summary", ""),
                    "finding_title": response.get("finding", {}).get("title", ""),
                    "finding_summary": response.get("finding", {}).get("summary", ""),
                    "recommendation": response.get("finding", {}).get("recommendation", ""),
                }
            )
        ConversationMemoryService.bootstrap_from_history(session_id, memory_turns)

    def _require_session(self, *, session_id: str, user_id: str):
        session = chat_crud.get_session_for_user(self.db, session_id, user_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
        return session

    @staticmethod
    def _serialize_session_summary(session) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "session_title": session.session_title,
            "turn_count": session.turn_count,
            "workspace_id": session.workspace_id,
            "connection_id": session.connection_id,
            "last_message_preview": session.last_message_preview,
            "created_at": ChatSessionService._format_dt(session.created_at),
            "updated_at": ChatSessionService._format_dt(session.updated_at),
            "last_message_at": ChatSessionService._format_dt(session.last_message_at),
            "is_archived": session.is_archived,
        }

    @staticmethod
    def _serialize_turn(turn) -> dict[str, Any]:
        response_payload = ChatSessionService._normalize_response_payload(turn.response_payload or {}, turn.session_id)
        return {
            "turn_id": turn.turn_id,
            "turn_index": turn.turn_index,
            "timestamp": ChatSessionService._format_dt(turn.created_at),
            "user_message": turn.user_message,
            "assistant_message": turn.assistant_message,
            "assistant_mode": turn.assistant_mode,
            "is_followup": turn.is_followup,
            "resolved_query": turn.resolved_query,
            "response": response_payload,
        }

    @staticmethod
    def _normalize_response_payload(response_payload: dict[str, Any], session_id: str) -> dict[str, Any]:
        normalized = dict(response_payload or {})
        normalized.setdefault("session_id", session_id)
        normalized.setdefault("session_title", "")
        normalized.setdefault("is_followup", False)
        normalized.setdefault("resolved_query", normalized.get("query", ""))
        normalized.setdefault("original_query", normalized.get("query", ""))
        normalized.setdefault("assistant_message", normalized.get("final_response", ""))
        normalized.setdefault("conversation_mode", "audit")
        normalized.setdefault("injected_context", {})
        normalized.setdefault("suggested_actions", [])
        normalized.setdefault("investigation_state", {})
        normalized.setdefault("turn_count", 1)
        normalized.setdefault("success", True)
        return normalized

    @staticmethod
    def _format_dt(value) -> str | None:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
