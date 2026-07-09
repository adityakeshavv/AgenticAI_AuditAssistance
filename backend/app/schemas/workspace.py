from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    workspace_name: str
    description: str | None = None
    selected_connection_ids: list[str] = Field(default_factory=list)
    active_connection_id: str | None = None


class WorkspaceSelectionUpdate(BaseModel):
    selected_connection_ids: list[str] = Field(default_factory=list)
    active_connection_id: str | None = None
    is_default: bool | None = None


class WorkspaceResponse(BaseModel):
    workspace_id: str
    workspace_name: str
    description: str | None = None
    selected_connection_ids: list[str] = Field(default_factory=list)
    active_connection_id: str | None = None
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMutationResponse(BaseModel):
    success: bool
    message: str | None = None
    workspace: WorkspaceResponse


class WorkspaceListResponse(BaseModel):
    workspaces: list[WorkspaceResponse] = Field(default_factory=list)
