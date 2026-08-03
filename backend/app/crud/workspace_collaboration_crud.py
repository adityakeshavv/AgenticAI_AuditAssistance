from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.workspace_collaboration import WorkspaceCollaborationItem


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_workspace_items(
    db: Session,
    *,
    workspace_id: str,
    item_type: str | None = None,
) -> list[WorkspaceCollaborationItem]:
    stmt = select(WorkspaceCollaborationItem).where(WorkspaceCollaborationItem.workspace_id == workspace_id)
    if item_type:
        stmt = stmt.where(WorkspaceCollaborationItem.item_type == item_type)
    stmt = stmt.order_by(
        WorkspaceCollaborationItem.created_at.desc(),
        WorkspaceCollaborationItem.updated_at.desc(),
    )
    return list(db.scalars(stmt).all())


def get_workspace_item(db: Session, collaboration_id: str, *, workspace_id: str | None = None) -> WorkspaceCollaborationItem | None:
    stmt = select(WorkspaceCollaborationItem).where(WorkspaceCollaborationItem.collaboration_id == collaboration_id)
    if workspace_id:
        stmt = stmt.where(WorkspaceCollaborationItem.workspace_id == workspace_id)
    return db.scalar(stmt)


def create_workspace_item(
    db: Session,
    *,
    workspace_id: str,
    item_type: str,
    title: str | None = None,
    body: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    mentions: list[str] | None = None,
    assignee_user_id: str | None = None,
    created_by_user_id: str | None = None,
    due_date=None,
) -> WorkspaceCollaborationItem:
    item = WorkspaceCollaborationItem(
        collaboration_id=str(uuid4()),
        workspace_id=workspace_id,
        item_type=item_type.strip().lower(),
        title=(title or "").strip() or None,
        body=(body or "").strip() or None,
        status=(status or "").strip() or None,
        priority=(priority or "").strip() or None,
        mentions=mentions or [],
        assignee_user_id=assignee_user_id or None,
        created_by_user_id=created_by_user_id or None,
        due_date=due_date,
        resolved_at=_now() if str(status or "").strip().lower() in {"resolved", "done", "closed", "approved"} else None,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(item)
    db.flush()
    return item


def update_workspace_item(
    db: Session,
    item: WorkspaceCollaborationItem,
    *,
    title: str | None = None,
    body: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    mentions: list[str] | None = None,
    assignee_user_id: str | None = None,
    due_date=None,
) -> WorkspaceCollaborationItem:
    if title is not None:
        item.title = title.strip() or None
    if body is not None:
        item.body = body.strip() or None
    if status is not None:
        item.status = status.strip() or None
        item.resolved_at = _now() if item.status and item.status.lower() in {"resolved", "done", "closed", "approved"} else None
    if priority is not None:
        item.priority = priority.strip() or None
    if mentions is not None:
        item.mentions = mentions
    if assignee_user_id is not None:
        item.assignee_user_id = assignee_user_id or None
    if due_date is not None:
        item.due_date = due_date
    item.updated_at = _now()
    db.add(item)
    db.flush()
    return item


def delete_workspace_item(db: Session, item: WorkspaceCollaborationItem) -> None:
    db.delete(item)
    db.flush()


def delete_workspace_items_for_workspace(db: Session, workspace_id: str) -> int:
    stmt = delete(WorkspaceCollaborationItem).where(WorkspaceCollaborationItem.workspace_id == workspace_id)
    result = db.execute(stmt)
    return result.rowcount or 0

