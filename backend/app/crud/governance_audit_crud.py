from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.governance_audit import GovernanceAuditLog


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_audit_event(
    db: Session,
    *,
    actor_user_id: str | None = None,
    actor_name: str | None = None,
    action_type: str,
    entity_type: str,
    entity_id: str | None = None,
    workspace_id: str | None = None,
    connection_id: str | None = None,
    severity: str = "info",
    summary: str,
    before_state: dict | None = None,
    after_state: dict | None = None,
) -> GovernanceAuditLog:
    event = GovernanceAuditLog(
        audit_log_id=str(uuid4()),
        actor_user_id=actor_user_id,
        actor_name=actor_name,
        action_type=action_type.strip(),
        entity_type=entity_type.strip(),
        entity_id=entity_id,
        workspace_id=workspace_id,
        connection_id=connection_id,
        severity=severity.strip().lower() or "info",
        summary=summary.strip(),
        before_state=before_state,
        after_state=after_state,
        created_at=_now(),
    )
    db.add(event)
    db.flush()
    return event


def list_audit_events(
    db: Session,
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
    stmt: Select[tuple[GovernanceAuditLog]] = select(GovernanceAuditLog).order_by(GovernanceAuditLog.created_at.desc())
    if action_type:
        stmt = stmt.where(GovernanceAuditLog.action_type == action_type)
    if entity_type:
        stmt = stmt.where(GovernanceAuditLog.entity_type == entity_type)
    if severity:
        stmt = stmt.where(GovernanceAuditLog.severity == severity)
    if actor_user_id:
        stmt = stmt.where(GovernanceAuditLog.actor_user_id == actor_user_id)
    if entity_id:
        stmt = stmt.where(GovernanceAuditLog.entity_id == entity_id)
    if workspace_id:
        stmt = stmt.where(GovernanceAuditLog.workspace_id == workspace_id)
    if connection_id:
        stmt = stmt.where(GovernanceAuditLog.connection_id == connection_id)
    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            GovernanceAuditLog.summary.ilike(needle)
            | GovernanceAuditLog.action_type.ilike(needle)
            | GovernanceAuditLog.entity_type.ilike(needle)
            | GovernanceAuditLog.entity_id.ilike(needle)
            | GovernanceAuditLog.actor_name.ilike(needle)
        )
    stmt = stmt.limit(max(1, min(limit, 500)))
    if offset > 0:
        stmt = stmt.offset(offset)
    return list(db.scalars(stmt).all())
