from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat_session import ChatSession
from app.models.chat_turn import ChatTurn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_session_title(message: str | None) -> str:
    if not message:
        return "New chat"
    cleaned = " ".join(message.strip().split())
    if len(cleaned) <= 40:
        return cleaned
    return f"{cleaned[:37].rstrip()}..."


def get_session(db: Session, session_id: str) -> ChatSession | None:
    return db.get(ChatSession, session_id)


def get_session_for_user(db: Session, session_id: str, user_id: str) -> ChatSession | None:
    stmt = select(ChatSession).where(ChatSession.session_id == session_id, ChatSession.user_id == user_id)
    return db.scalar(stmt)


def list_sessions_for_user(db: Session, user_id: str) -> list[ChatSession]:
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id, ChatSession.is_archived.is_(False))
        .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def create_session(
    db: Session,
    *,
    user_id: str,
    workspace_id: str | None = None,
    connection_id: str | None = None,
    session_title: str = "New chat",
) -> ChatSession:
    session = ChatSession(
        session_id=str(uuid4()),
        user_id=user_id,
        workspace_id=workspace_id,
        connection_id=connection_id,
        session_title=session_title or "New chat",
        last_message_preview=None,
        turn_count=0,
        is_archived=False,
        created_at=_now(),
        updated_at=_now(),
        last_message_at=None,
    )
    db.add(session)
    db.flush()
    return session


def update_session_touch(
    db: Session,
    session: ChatSession,
    *,
    workspace_id: str | None = None,
    connection_id: str | None = None,
    session_title: str | None = None,
    last_message_preview: str | None = None,
) -> ChatSession:
    if workspace_id is not None:
        session.workspace_id = workspace_id
    if connection_id is not None:
        session.connection_id = connection_id
    if session_title is not None:
        session.session_title = session_title
    if last_message_preview is not None:
        session.last_message_preview = last_message_preview
    session.updated_at = _now()
    session.last_message_at = _now()
    db.add(session)
    db.flush()
    return session


def archive_session(db: Session, session: ChatSession) -> ChatSession:
    session.is_archived = True
    session.updated_at = _now()
    db.add(session)
    db.flush()
    return session


def list_turns(db: Session, session_id: str) -> list[ChatTurn]:
    stmt = select(ChatTurn).where(ChatTurn.session_id == session_id).order_by(ChatTurn.turn_index.asc())
    return list(db.scalars(stmt).all())


def append_turn(
    db: Session,
    session: ChatSession,
    *,
    user_message: str,
    assistant_message: str,
    assistant_mode: str,
    is_followup: bool,
    resolved_query: str,
    response_payload: dict,
) -> ChatTurn:
    turn = ChatTurn(
        turn_id=str(uuid4()),
        session_id=session.session_id,
        turn_index=session.turn_count + 1,
        user_message=user_message,
        assistant_message=assistant_message,
        assistant_mode=assistant_mode,
        is_followup=is_followup,
        resolved_query=resolved_query,
        response_payload=response_payload,
        created_at=_now(),
    )
    db.add(turn)
    session.turn_count += 1
    session.last_message_preview = assistant_message or user_message
    if session.session_title == "New chat":
        session.session_title = _build_session_title(user_message)
    session.updated_at = _now()
    session.last_message_at = _now()
    db.add(session)
    db.flush()
    return turn
