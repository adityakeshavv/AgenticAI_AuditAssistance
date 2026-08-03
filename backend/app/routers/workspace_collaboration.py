from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.auth import require_workspace_access
from app.dependencies.database import get_db
from app.schemas.auth import AuthUser
from app.schemas.workspace_collaboration import (
    WorkspaceCollaborationCreate,
    WorkspaceCollaborationListResponse,
    WorkspaceCollaborationResponse,
    WorkspaceCollaborationUpdate,
)
from app.services.workspace_collaboration_service import WorkspaceCollaborationService


router = APIRouter(prefix="/workspaces/{workspace_id}/collaboration", tags=["workspace-collaboration"])


@router.get("", response_model=WorkspaceCollaborationListResponse)
def list_collaboration_items(
    workspace_id: str,
    item_type: str | None = None,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_workspace_access),
) -> dict:
    svc = WorkspaceCollaborationService(db)
    return svc.list_items(workspace_id=workspace_id, item_type=item_type)


@router.post("", response_model=WorkspaceCollaborationResponse)
def create_collaboration_item(
    workspace_id: str,
    payload: WorkspaceCollaborationCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_workspace_access),
) -> dict:
    svc = WorkspaceCollaborationService(db)
    result = svc.create_item(workspace_id=workspace_id, actor=current_user, payload=payload.model_dump())
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message", "Unable to save collaboration item."))
    return WorkspaceCollaborationResponse(**result["item"])


@router.patch("/{collaboration_id}", response_model=WorkspaceCollaborationResponse)
def update_collaboration_item(
    workspace_id: str,
    collaboration_id: str,
    payload: WorkspaceCollaborationUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_workspace_access),
) -> dict:
    svc = WorkspaceCollaborationService(db)
    result = svc.update_item(
        workspace_id=workspace_id,
        collaboration_id=collaboration_id,
        actor=current_user,
        payload=payload.model_dump(exclude_unset=True),
    )
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message", "Collaboration item not found."))
    return WorkspaceCollaborationResponse(**result["item"])


@router.delete("/{collaboration_id}")
def delete_collaboration_item(
    workspace_id: str,
    collaboration_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_workspace_access),
) -> dict:
    svc = WorkspaceCollaborationService(db)
    result = svc.delete_item(workspace_id=workspace_id, collaboration_id=collaboration_id, actor=current_user)
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message", "Collaboration item not found."))
    return {"success": True}
