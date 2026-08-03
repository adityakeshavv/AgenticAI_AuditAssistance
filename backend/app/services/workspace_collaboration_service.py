from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.crud import audit_workspace_crud, user_crud, workspace_collaboration_crud
from app.schemas.auth import AuthUser
from app.services.governance_audit_service import GovernanceAuditService


class WorkspaceCollaborationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_items(self, *, workspace_id: str, item_type: str | None = None) -> dict[str, Any]:
        items = workspace_collaboration_crud.list_workspace_items(self.db, workspace_id=workspace_id, item_type=item_type)
        return {
            "items": [self.serialize_item(item) for item in items],
            "summary": self.summarize_workspace(workspace_id=workspace_id),
        }

    def create_item(self, *, workspace_id: str, actor: AuthUser, payload: dict[str, Any]) -> dict[str, Any]:
        workspace = audit_workspace_crud.get_workspace_by_id(self.db, workspace_id)
        if workspace is None:
            return {"success": False, "message": "Workspace not found."}

        item = workspace_collaboration_crud.create_workspace_item(
            self.db,
            workspace_id=workspace_id,
            item_type=str(payload.get("item_type") or "comment"),
            title=self._text(payload.get("title")),
            body=self._text(payload.get("body")),
            status=self._text(payload.get("status")),
            priority=self._text(payload.get("priority")),
            mentions=self._normalize_mentions(payload.get("mentions")),
            assignee_user_id=self._text(payload.get("assignee_user_id")) or None,
            created_by_user_id=actor.user_id,
            due_date=self._normalize_date(payload.get("due_date")),
        )

        GovernanceAuditService(self.db).record_event(
            actor_user_id=actor.user_id,
            actor_name=self._actor_name(actor.user_id),
            action_type="workspace_collaboration_created",
            entity_type="workspace_collaboration_item",
            entity_id=item.collaboration_id,
            workspace_id=workspace_id,
            severity="info",
            summary=f"A {item.item_type} item was added to workspace '{workspace.workspace_name}'.",
            after_state=self.serialize_item(item),
        )
        self.db.commit()
        return {"success": True, "item": self.serialize_item(item), "summary": self.summarize_workspace(workspace_id=workspace_id)}

    def update_item(self, *, workspace_id: str, collaboration_id: str, actor: AuthUser, payload: dict[str, Any]) -> dict[str, Any]:
        item = workspace_collaboration_crud.get_workspace_item(self.db, collaboration_id, workspace_id=workspace_id)
        if item is None:
            return {"success": False, "message": "Collaboration item not found."}

        before = self.serialize_item(item)
        workspace_collaboration_crud.update_workspace_item(
            self.db,
            item,
            title=self._text(payload.get("title")) if "title" in payload else None,
            body=self._text(payload.get("body")) if "body" in payload else None,
            status=self._text(payload.get("status")) if "status" in payload else None,
            priority=self._text(payload.get("priority")) if "priority" in payload else None,
            mentions=self._normalize_mentions(payload.get("mentions")) if "mentions" in payload else None,
            assignee_user_id=self._text(payload.get("assignee_user_id")) if "assignee_user_id" in payload else None,
            due_date=self._normalize_date(payload.get("due_date")) if "due_date" in payload else None,
        )

        GovernanceAuditService(self.db).record_event(
            actor_user_id=actor.user_id,
            actor_name=self._actor_name(actor.user_id),
            action_type="workspace_collaboration_updated",
            entity_type="workspace_collaboration_item",
            entity_id=item.collaboration_id,
            workspace_id=workspace_id,
            severity="info",
            summary=f"A {item.item_type} item was updated in the workspace.",
            before_state=before,
            after_state=self.serialize_item(item),
        )
        self.db.commit()
        return {"success": True, "item": self.serialize_item(item), "summary": self.summarize_workspace(workspace_id=workspace_id)}

    def delete_item(self, *, workspace_id: str, collaboration_id: str, actor: AuthUser) -> dict[str, Any]:
        item = workspace_collaboration_crud.get_workspace_item(self.db, collaboration_id, workspace_id=workspace_id)
        if item is None:
            return {"success": False, "message": "Collaboration item not found."}

        payload = self.serialize_item(item)
        workspace_collaboration_crud.delete_workspace_item(self.db, item)

        GovernanceAuditService(self.db).record_event(
            actor_user_id=actor.user_id,
            actor_name=self._actor_name(actor.user_id),
            action_type="workspace_collaboration_deleted",
            entity_type="workspace_collaboration_item",
            entity_id=collaboration_id,
            workspace_id=workspace_id,
            severity="warning",
            summary=f"A {item.item_type} item was removed from the workspace.",
            before_state=payload,
        )
        self.db.commit()
        return {"success": True, "summary": self.summarize_workspace(workspace_id=workspace_id)}

    def summarize_workspace(self, *, workspace_id: str) -> dict[str, Any]:
        items = workspace_collaboration_crud.list_workspace_items(self.db, workspace_id=workspace_id)
        counts: dict[str, int] = {"comment": 0, "task": 0, "review": 0}
        open_items = 0
        completed_items = 0
        mention_count = 0
        for item in items:
            item_type = (item.item_type or "comment").strip().lower()
            counts[item_type] = counts.get(item_type, 0) + 1
            status = (item.status or "").strip().lower()
            if status in {"resolved", "done", "closed", "approved"}:
                completed_items += 1
            else:
                open_items += 1
            mention_count += len(item.mentions or [])

        return {
            "total_items": len(items),
            "open_items": open_items,
            "completed_items": completed_items,
            "comment_count": counts.get("comment", 0),
            "task_count": counts.get("task", 0),
            "review_count": counts.get("review", 0),
            "mention_count": mention_count,
        }

    def serialize_item(self, item) -> dict[str, Any]:
        return {
            "collaboration_id": item.collaboration_id,
            "workspace_id": item.workspace_id,
            "item_type": item.item_type,
            "title": item.title,
            "body": item.body,
            "status": item.status,
            "priority": item.priority,
            "mentions": list(item.mentions or []),
            "assignee_user_id": item.assignee_user_id,
            "created_by_user_id": item.created_by_user_id,
            "due_date": item.due_date.isoformat() if item.due_date else None,
            "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }

    def _normalize_mentions(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        mentions: list[str] = []
        seen: set[str] = set()
        for entry in value:
            text = self._text(entry)
            if not text or text in seen:
                continue
            seen.add(text)
            mentions.append(text)
        return mentions

    def _normalize_date(self, value: Any) -> date | None:
        if value in {None, ""}:
            return None
        if isinstance(value, date):
            return value
        text = self._text(value)
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None

    def _text(self, value: Any) -> str:
        return str(value or "").strip()

    def _actor_name(self, user_id: str) -> str | None:
        user = user_crud.get_user_by_id(self.db, user_id)
        if user is None:
            return None
        return user.full_name or user.email
