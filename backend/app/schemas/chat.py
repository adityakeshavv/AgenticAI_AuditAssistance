from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.audit import (
    AuditResponse,
    CitationRecord,
    EvaluationRecord,
    ExecutionMetadataRecord,
    TraceabilityRecord,
)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    page: int = 1
    page_size: int = 10
    connection_id: str | None = None
    workspace_id: str | None = None
    attached_document_ids: list[str] = Field(default_factory=list)


class SuggestedAction(BaseModel):
    id: str
    label: str
    description: str

    model_config = ConfigDict(from_attributes=True)


class ChatSessionSummary(BaseModel):
    session_id: str
    session_title: str
    turn_count: int = 0
    workspace_id: str | None = None
    connection_id: str | None = None
    last_message_preview: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    last_message_at: str | None = None
    is_archived: bool = False

    model_config = ConfigDict(from_attributes=True)


class ChatTurnRecord(BaseModel):
    turn_id: str
    turn_index: int
    timestamp: str | None = None
    user_message: str
    assistant_message: str
    assistant_mode: str = "audit"
    is_followup: bool = False
    resolved_query: str | None = None
    response: "ChatResponse"

    model_config = ConfigDict(from_attributes=True)


class ChatHistoryResponse(BaseModel):
    session_id: str
    session_title: str
    turn_count: int = 0
    workspace_id: str | None = None
    connection_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    last_message_at: str | None = None
    turns: list[ChatTurnRecord] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class InvestigationState(BaseModel):
    entity_type: str | None = None
    entity_ids: list[str] = Field(default_factory=list)
    transaction_ids: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    risk_rating: str | None = None
    transaction_count: int = 0
    document_count: int = 0
    finding_count: int = 0
    key_findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    status: str = "idle"

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(AuditResponse):
    """Extends AuditResponse with conversation-layer fields."""
    session_id: str
    session_title: str = ""
    is_followup: bool = False
    resolved_query: str = ""
    original_query: str = ""
    assistant_message: str = ""
    conversation_mode: str = "audit"
    injected_context: dict[str, Any] = Field(default_factory=dict)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    investigation_state: InvestigationState = Field(default_factory=InvestigationState)
    turn_count: int = 1

    model_config = ConfigDict(from_attributes=True)
