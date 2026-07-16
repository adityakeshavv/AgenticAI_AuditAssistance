from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.crud import governance_audit_crud, user_crud
from app.models.governance_audit import GovernanceAuditLog


logger = logging.getLogger(__name__)


class GovernanceAuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record_event(
        self,
        *,
        actor_user_id: str | None = None,
        action_type: str,
        entity_type: str,
        summary: str,
        entity_id: str | None = None,
        workspace_id: str | None = None,
        connection_id: str | None = None,
        severity: str = "info",
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        actor_name: str | None = None,
    ) -> GovernanceAuditLog | None:
        try:
            resolved_actor_name = actor_name or self._resolve_actor_name(actor_user_id)
            event = governance_audit_crud.create_audit_event(
                self.db,
                actor_user_id=actor_user_id,
                actor_name=resolved_actor_name,
                action_type=action_type,
                entity_type=entity_type,
                entity_id=entity_id,
                workspace_id=workspace_id,
                connection_id=connection_id,
                severity=severity,
                summary=summary,
                before_state=before_state,
                after_state=after_state,
            )
            return event
        except Exception as exc:  # pragma: no cover - audit logging must never block primary actions
            logger.debug("Governance audit event was not recorded: %s", exc)
            return None

    def list_events(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        action_type: str | None = None,
        entity_type: str | None = None,
        severity: str | None = None,
        actor_user_id: str | None = None,
        entity_id: str | None = None,
        workspace_id: str | None = None,
        connection_id: str | None = None,
        search: str | None = None,
    ) -> list[GovernanceAuditLog]:
        return governance_audit_crud.list_audit_events(
            self.db,
            limit=limit,
            offset=offset,
            action_type=action_type,
            entity_type=entity_type,
            severity=severity,
            actor_user_id=actor_user_id,
            entity_id=entity_id,
            workspace_id=workspace_id,
            connection_id=connection_id,
            search=search,
        )

    def serialize_event(self, event: GovernanceAuditLog) -> dict[str, Any]:
        return {
            "audit_log_id": event.audit_log_id,
            "actor_user_id": event.actor_user_id,
            "actor_name": event.actor_name,
            "action_type": event.action_type,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "workspace_id": event.workspace_id,
            "connection_id": event.connection_id,
            "severity": event.severity,
            "summary": event.summary,
            "before_state": event.before_state,
            "after_state": event.after_state,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }

    def _resolve_actor_name(self, actor_user_id: str | None) -> str | None:
        if not actor_user_id:
            return None
        user = user_crud.get_user_by_id(self.db, actor_user_id)
        if user is None:
            return None
        return user.full_name or user.email
