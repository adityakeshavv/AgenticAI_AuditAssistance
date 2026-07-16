from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GovernanceAuditRecord(BaseModel):
    audit_log_id: str
    actor_user_id: str | None = None
    actor_name: str | None = None
    action_type: str
    entity_type: str
    entity_id: str | None = None
    workspace_id: str | None = None
    connection_id: str | None = None
    severity: str
    summary: str
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GovernanceAuditListResponse(BaseModel):
    events: list[GovernanceAuditRecord] = Field(default_factory=list)

