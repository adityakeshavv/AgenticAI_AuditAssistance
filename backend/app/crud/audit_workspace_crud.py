from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_workspace import AuditWorkspace
from app.models.database_connection import DatabaseConnection


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_workspaces_for_user(db: Session, user_id: str) -> list[AuditWorkspace]:
    stmt = select(AuditWorkspace).where(AuditWorkspace.owner_user_id == user_id).order_by(
        AuditWorkspace.is_default.desc(),
        AuditWorkspace.created_at.desc(),
    )
    return list(db.scalars(stmt).all())


def list_all_workspaces(db: Session) -> list[AuditWorkspace]:
    stmt = select(AuditWorkspace).order_by(
        AuditWorkspace.is_default.desc(),
        AuditWorkspace.created_at.desc(),
    )
    return list(db.scalars(stmt).all())


def get_workspace_by_id(db: Session, workspace_id: str, *, user_id: str | None = None) -> AuditWorkspace | None:
    stmt = select(AuditWorkspace).where(AuditWorkspace.workspace_id == workspace_id)
    if user_id:
        stmt = stmt.where(AuditWorkspace.owner_user_id == user_id)
    return db.scalar(stmt)


def create_workspace(
    db: Session,
    *,
    owner_user_id: str,
    workspace_name: str,
    description: str | None = None,
    selected_connection_ids: list[str] | None = None,
    active_connection_id: str | None = None,
    is_default: bool = False,
    is_active: bool = True,
) -> AuditWorkspace:
    workspace = AuditWorkspace(
        workspace_id=str(uuid4()),
        owner_user_id=owner_user_id,
        workspace_name=workspace_name.strip(),
        description=(description or "").strip() or None,
        selected_connection_ids=selected_connection_ids or [],
        active_connection_id=active_connection_id,
        is_default=is_default,
        is_active=is_active,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(workspace)
    db.flush()
    return workspace


def update_workspace_selection(
    db: Session,
    workspace: AuditWorkspace,
    *,
    selected_connection_ids: list[str] | None = None,
    active_connection_id: str | None = None,
) -> AuditWorkspace:
    if selected_connection_ids is not None:
        workspace.selected_connection_ids = selected_connection_ids
    if active_connection_id is not None:
        workspace.active_connection_id = active_connection_id
    workspace.updated_at = _now()
    db.add(workspace)
    db.flush()
    return workspace


def set_default_workspace(db: Session, *, user_id: str, workspace_id: str) -> AuditWorkspace | None:
    workspaces = list_workspaces_for_user(db, user_id)
    target = next((workspace for workspace in workspaces if workspace.workspace_id == workspace_id), None)
    if target is None:
        return None

    for workspace in workspaces:
        workspace.is_default = workspace.workspace_id == workspace_id
        workspace.updated_at = _now()
        db.add(workspace)
    db.flush()
    return target


def delete_workspace(db: Session, workspace: AuditWorkspace) -> None:
    db.delete(workspace)
    db.flush()


def validate_selected_connections(db: Session, *, user_id: str, connection_ids: list[str]) -> list[str]:
    if not connection_ids:
        return []
    stmt = select(DatabaseConnection.connection_id).where(
        DatabaseConnection.owner_user_id == user_id,
        DatabaseConnection.connection_id.in_(connection_ids),
    )
    return list(db.scalars(stmt).all())
