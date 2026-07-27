from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.schemas.chat import ChatHistoryResponse, ChatRequest, ChatResponse, ChatSessionSummary
from app.services.chat_service import ChatService
from app.services.chat_session_service import ChatSessionService


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatResponse)
def chat_message(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
) -> dict:
    svc = ChatService(db)
    return svc.chat(
        message=payload.message,
        session_id=payload.session_id,
        page=payload.page,
        page_size=payload.page_size,
        user_id=current_user.user_id,
        user_name=current_user.full_name,
        connection_id=payload.connection_id,
        workspace_id=payload.workspace_id,
        attached_document_ids=payload.attached_document_ids,
    )


@router.post("/session")
def create_session(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
) -> dict:
    session = ChatSessionService(db).create_session(user_id=current_user.user_id)
    return session


@router.get("/sessions", response_model=list[ChatSessionSummary])
def list_sessions(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
) -> list[dict]:
    return ChatSessionService(db).list_sessions(user_id=current_user.user_id)


@router.get("/session/{session_id}/history", response_model=ChatHistoryResponse)
def get_session_history(
    session_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
) -> dict:
    return ChatSessionService(db).get_history(session_id=session_id, user_id=current_user.user_id)


@router.delete("/session/{session_id}")
def clear_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
) -> dict:
    return ChatSessionService(db).archive_session(session_id=session_id, user_id=current_user.user_id)
