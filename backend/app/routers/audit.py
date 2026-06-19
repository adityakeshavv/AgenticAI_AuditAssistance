from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.schemas.audit import AuditQueryRequest, AuditResponse
from app.services.agent_service import AgentService


router = APIRouter(prefix="/audit", tags=["audit"])


@router.post("/query", response_model=AuditResponse)
def audit_query(payload: AuditQueryRequest, db: Session = Depends(get_db)) -> AuditResponse:
    service = AgentService(db)
    return service.run(query=payload.query, page=payload.page, page_size=payload.page_size)
