from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCollaborationCreate(BaseModel):
    item_type: str
    title: str | None = None
    body: str | None = None
    status: str | None = None
    priority: str | None = None
    mentions: list[str] = Field(default_factory=list)
    assignee_user_id: str | None = None
    due_date: date | None = None


class WorkspaceCollaborationUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    status: str | None = None
    priority: str | None = None
    mentions: list[str] | None = None
    assignee_user_id: str | None = None
    due_date: date | None = None


class WorkspaceCollaborationResponse(BaseModel):
    collaboration_id: str
    workspace_id: str
    item_type: str
    title: str | None = None
    body: str | None = None
    status: str | None = None
    priority: str | None = None
    mentions: list[str] = Field(default_factory=list)
    assignee_user_id: str | None = None
    created_by_user_id: str | None = None
    due_date: date | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceCollaborationListResponse(BaseModel):
    items: list[WorkspaceCollaborationResponse] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
