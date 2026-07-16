from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.schemas.audit import AuditQueryRequest, AuditResponse
from app.services.database_connector_service import DatabaseConnectorService
from app.services.agent_service import AgentService


router = APIRouter(prefix="/audit", tags=["audit"])


@router.post("/query", response_model=AuditResponse)
def audit_query(
    payload: AuditQueryRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
) -> AuditResponse:
    connector = DatabaseConnectorService(db)
    with connector.open_session(
        user_id=current_user.user_id,
        connection_id=payload.connection_id,
        workspace_id=payload.workspace_id,
    ) as data_db:
        service = AgentService(data_db, audit_db=db)
        try:
            return service.run(query=payload.query, page=payload.page, page_size=payload.page_size, actor_user_id=current_user.user_id)
        except Exception as exc:
            from app.services.governance_audit_service import GovernanceAuditService

            GovernanceAuditService(db).record_event(
                actor_user_id=current_user.user_id,
                action_type="audit_query_failed",
                entity_type="audit_query",
                severity="warning",
                summary=f"Audit query failed: {payload.query[:200]}",
                after_state={"query": payload.query, "error": str(exc)},
            )
            db.commit()
            raise
