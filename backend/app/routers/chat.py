from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.services.conversation_memory_service import ConversationMemoryService


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatResponse)
def chat_message(payload: ChatRequest, db: Session = Depends(get_db)) -> dict:
    svc = ChatService(db)
    return svc.chat(
        message=payload.message,
        session_id=payload.session_id,
        page=payload.page,
        page_size=payload.page_size,
    )


@router.post("/session")
def create_session() -> dict:
    session_id = ConversationMemoryService.create_session()
    return {"session_id": session_id}


@router.get("/session/{session_id}/history")
def get_session_history(session_id: str) -> dict:
    session = ConversationMemoryService.get_session(session_id)
    if not session:
        return {"error": "Session not found", "session_id": session_id}
    turns = session["session"]["turns"]
    investigation = dict(session["investigation"])
    investigation["entity_ids"] = list(investigation.get("entity_ids", set()))
    investigation["transaction_ids"] = list(investigation.get("transaction_ids", set()))
    return {
        "session_id": session_id,
        "turn_count": len(turns),
        "turns": [
            {
                "turn_id": t["turn_id"],
                "timestamp": t["timestamp"],
                "user": t["user"],
                "summary": t["assistant_summary"],
                "risk_rating": t["risk_rating"],
                "finding_title": t["finding_title"],
            }
            for t in turns
        ],
        "investigation": investigation,
    }


@router.delete("/session/{session_id}")
def clear_session(session_id: str) -> dict:
    from app.services.conversation_memory_service import ConversationMemoryService as CMS
    if session_id in CMS._sessions:
        del CMS._sessions[session_id]
        return {"cleared": True, "session_id": session_id}
    return {"cleared": False, "session_id": session_id}
