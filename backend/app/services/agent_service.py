from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.audit_workflow_service import AuditWorkflowService


class AgentService:
    """Facade for the main audit workflow.

    The actual execution logic lives in AuditWorkflowService so this class
    stays small and easy to read.
    """

    def __init__(self, db: Session, *, audit_db: Session | None = None) -> None:
        self.workflow = AuditWorkflowService(db, audit_db=audit_db)

    def run(
        self,
        *,
        query: str,
        page: int = 1,
        page_size: int = 10,
        actor_user_id: str | None = None,
        attached_document_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.workflow.run(
            query=query,
            page=page,
            page_size=page_size,
            actor_user_id=actor_user_id,
            attached_document_ids=attached_document_ids,
        )
