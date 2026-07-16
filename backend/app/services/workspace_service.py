from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.crud import audit_workspace_crud, database_connection_crud
from app.models.audit_workspace import AuditWorkspace
from app.crud import user_crud
from app.services.governance_audit_service import GovernanceAuditService


class WorkspaceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_workspaces(self, user_id: str) -> list[dict[str, Any]]:
        return [self.serialize_workspace(workspace) for workspace in audit_workspace_crud.list_workspaces_for_user(self.db, user_id)]

    def list_all_workspaces(self) -> list[dict[str, Any]]:
        return [self.serialize_workspace(workspace) for workspace in audit_workspace_crud.list_all_workspaces(self.db)]

    def get_workspace(self, user_id: str, workspace_id: str) -> AuditWorkspace | None:
        return audit_workspace_crud.get_workspace_by_id(self.db, workspace_id, user_id=user_id)

    def create_workspace(self, *, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        selected_connection_ids = self._normalize_connection_ids(payload.get("selected_connection_ids"))
        active_connection_id = self._normalize_text(payload.get("active_connection_id"))
        if active_connection_id and active_connection_id not in selected_connection_ids:
            selected_connection_ids = [active_connection_id, *selected_connection_ids]

        selected_connection_ids = self._validate_connection_ids(user_id=user_id, connection_ids=selected_connection_ids)
        if active_connection_id and active_connection_id not in selected_connection_ids:
            active_connection_id = None
        if not active_connection_id and selected_connection_ids:
            active_connection_id = selected_connection_ids[0]

        existing_workspaces = audit_workspace_crud.list_workspaces_for_user(self.db, user_id)
        is_default = not existing_workspaces or not any(workspace.is_default for workspace in existing_workspaces)
        workspace = audit_workspace_crud.create_workspace(
            self.db,
            owner_user_id=user_id,
            workspace_name=str(payload.get("workspace_name", "")).strip(),
            description=str(payload.get("description", "")).strip() or None,
            selected_connection_ids=selected_connection_ids,
            active_connection_id=active_connection_id,
            is_default=is_default,
            is_active=True,
        )
        GovernanceAuditService(self.db).record_event(
            actor_user_id=user_id,
            action_type="workspace_created",
            entity_type="workspace",
            entity_id=workspace.workspace_id,
            workspace_id=workspace.workspace_id,
            severity="info",
            summary=f"Workspace '{workspace.workspace_name}' was created.",
            after_state=self.serialize_workspace(workspace),
            actor_name=self._actor_name(user_id),
        )
        self.db.commit()
        return {"success": True, "workspace": self.serialize_workspace(workspace)}

    def update_selection(
        self,
        *,
        user_id: str,
        workspace_id: str,
        selected_connection_ids: list[str] | None = None,
        active_connection_id: str | None = None,
        is_default: bool | None = None,
    ) -> dict[str, Any]:
        workspace = self.get_workspace(user_id, workspace_id)
        if workspace is None:
            return {"success": False, "message": "Workspace not found."}

        current_selected = list(workspace.selected_connection_ids or [])
        normalized_selected = None
        if selected_connection_ids is not None:
            normalized_selected = self._validate_connection_ids(
                user_id=user_id,
                connection_ids=self._normalize_connection_ids(selected_connection_ids),
            )
            current_selected = normalized_selected or current_selected

        if active_connection_id is not None:
            active_connection_id = self._normalize_text(active_connection_id)
            if active_connection_id not in current_selected:
                active_connection_id = current_selected[0] if current_selected else None
        elif current_selected:
            active_connection_id = current_selected[0]

        audit_workspace_crud.update_workspace_selection(
            self.db,
            workspace,
            selected_connection_ids=normalized_selected,
            active_connection_id=active_connection_id,
        )

        if is_default is True:
            audit_workspace_crud.set_default_workspace(self.db, user_id=user_id, workspace_id=workspace_id)
        elif is_default is False and workspace.is_default:
            workspace.is_default = False
            self.db.add(workspace)
            self.db.flush()

        GovernanceAuditService(self.db).record_event(
            actor_user_id=user_id,
            action_type="workspace_updated",
            entity_type="workspace",
            entity_id=workspace.workspace_id,
            workspace_id=workspace.workspace_id,
            severity="info",
            summary=f"Workspace '{workspace.workspace_name}' selection was updated.",
            after_state=self.serialize_workspace(workspace),
            actor_name=self._actor_name(user_id),
        )
        self.db.commit()
        return {"success": True, "workspace": self.serialize_workspace(workspace)}

    def activate_workspace(self, *, user_id: str, workspace_id: str) -> dict[str, Any]:
        workspace = audit_workspace_crud.set_default_workspace(self.db, user_id=user_id, workspace_id=workspace_id)
        if workspace is None:
            return {"success": False, "message": "Workspace not found."}
        GovernanceAuditService(self.db).record_event(
            actor_user_id=user_id,
            action_type="workspace_activated",
            entity_type="workspace",
            entity_id=workspace.workspace_id,
            workspace_id=workspace.workspace_id,
            severity="info",
            summary=f"Workspace '{workspace.workspace_name}' was activated.",
            after_state=self.serialize_workspace(workspace),
            actor_name=self._actor_name(user_id),
        )
        self.db.commit()
        return {"success": True, "workspace": self.serialize_workspace(workspace)}

    def delete_workspace(self, *, user_id: str, workspace_id: str) -> dict[str, Any]:
        workspace = self.get_workspace(user_id, workspace_id)
        if workspace is None:
            return {"success": False, "message": "Workspace not found."}
        was_default = workspace.is_default
        audit_workspace_crud.delete_workspace(self.db, workspace)
        if was_default:
            remaining = audit_workspace_crud.list_workspaces_for_user(self.db, user_id)
            if remaining:
                audit_workspace_crud.set_default_workspace(self.db, user_id=user_id, workspace_id=remaining[0].workspace_id)
        GovernanceAuditService(self.db).record_event(
            actor_user_id=user_id,
            action_type="workspace_deleted",
            entity_type="workspace",
            entity_id=workspace.workspace_id,
            workspace_id=workspace.workspace_id,
            severity="warning",
            summary=f"Workspace '{workspace.workspace_name}' was deleted.",
            before_state=self.serialize_workspace(workspace),
            actor_name=self._actor_name(user_id),
        )
        self.db.commit()
        return {"success": True}

    def serialize_workspace(self, workspace: AuditWorkspace) -> dict[str, Any]:
        return {
            "workspace_id": workspace.workspace_id,
            "workspace_name": workspace.workspace_name,
            "description": workspace.description,
            "selected_connection_ids": list(workspace.selected_connection_ids or []),
            "active_connection_id": workspace.active_connection_id,
            "is_default": workspace.is_default,
            "is_active": workspace.is_active,
            "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
            "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None,
        }

    def resolve_connection_id(self, *, user_id: str, connection_id: str | None = None, workspace_id: str | None = None) -> str | None:
        if connection_id:
            connection = database_connection_crud.get_connection_by_id(self.db, connection_id, user_id=user_id)
            if connection:
                return connection.connection_id
        if workspace_id:
            workspace = self.get_workspace(user_id, workspace_id)
            if workspace:
                if workspace.active_connection_id:
                    return workspace.active_connection_id
                if workspace.selected_connection_ids:
                    return workspace.selected_connection_ids[0]
        default_connection = database_connection_crud.get_default_connection_for_user(self.db, user_id)
        return default_connection.connection_id if default_connection else None

    def _normalize_connection_ids(self, values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = self._normalize_text(value)
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    def _normalize_text(self, value: Any) -> str:
        return str(value or "").strip()

    def _validate_connection_ids(self, *, user_id: str, connection_ids: list[str]) -> list[str]:
        valid_connection_ids: list[str] = []
        for connection_id in connection_ids:
            if database_connection_crud.get_connection_by_id(self.db, connection_id, user_id=user_id):
                valid_connection_ids.append(connection_id)
        return valid_connection_ids

    def _actor_name(self, user_id: str) -> str | None:
        user = user_crud.get_user_by_id(self.db, user_id)
        if user is None:
            return None
        return user.full_name or user.email
