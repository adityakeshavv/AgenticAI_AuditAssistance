from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_workspace_access
from app.dependencies.database import get_db
from app.schemas.auth import AuthUser
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceMutationResponse,
    WorkspaceResponse,
    WorkspaceSelectionUpdate,
)
from app.services.workspace_service import WorkspaceService


router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=WorkspaceListResponse)
def list_workspaces(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> dict:
    svc = WorkspaceService(db)
    return {"workspaces": svc.list_workspaces(current_user.user_id)}


@router.post("", response_model=WorkspaceMutationResponse)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> dict:
    svc = WorkspaceService(db)
    result = svc.create_workspace(user_id=current_user.user_id, payload=payload.model_dump())
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message", "Unable to save workspace."))
    return {"success": True, "message": "Workspace saved successfully.", "workspace": WorkspaceResponse(**result["workspace"])}


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_workspace_access),
) -> WorkspaceResponse:
    svc = WorkspaceService(db)
    workspace = svc.get_workspace(current_user.user_id, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return WorkspaceResponse(**svc.serialize_workspace(workspace))


@router.patch("/{workspace_id}/selection", response_model=WorkspaceMutationResponse)
def update_selection(
    workspace_id: str,
    payload: WorkspaceSelectionUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_workspace_access),
) -> dict:
    svc = WorkspaceService(db)
    result = svc.update_selection(
        user_id=current_user.user_id,
        workspace_id=workspace_id,
        selected_connection_ids=payload.selected_connection_ids,
        active_connection_id=payload.active_connection_id,
        is_default=payload.is_default,
    )
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message", "Workspace not found."))
    return {"success": True, "message": "Workspace selection saved.", "workspace": WorkspaceResponse(**result["workspace"])}


@router.post("/{workspace_id}/activate", response_model=WorkspaceMutationResponse)
def activate_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_workspace_access),
) -> dict:
    svc = WorkspaceService(db)
    result = svc.activate_workspace(user_id=current_user.user_id, workspace_id=workspace_id)
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message", "Workspace not found."))
    return {"success": True, "workspace": WorkspaceResponse(**result["workspace"])}


@router.delete("/{workspace_id}")
def delete_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_workspace_access),
) -> dict:
    svc = WorkspaceService(db)
    result = svc.delete_workspace(user_id=current_user.user_id, workspace_id=workspace_id)
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message", "Workspace not found."))
    return {"success": True}
