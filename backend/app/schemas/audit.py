from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditQueryRequest(BaseModel):
    query: str
    page: int = 1
    page_size: int = 10


class TraceabilityRecord(BaseModel):
    agents_invoked: list[str] = Field(default_factory=list)
    agent_selection_reasoning: list[str] = Field(default_factory=list)
    sources_used: list[str] = Field(default_factory=list)
    evidence_used: list[dict[str, Any]] = Field(default_factory=list)
    reasoning_path: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AuditResponse(BaseModel):
    success: bool = True
    query: str
    intent: dict[str, Any] = Field(default_factory=dict)
    agents_used: list[str] = Field(default_factory=list)
    structured_evidence: list[dict[str, Any]] = Field(default_factory=list)
    document_evidence: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    finding: str = ""
    final_response: str = ""
    traceability: TraceabilityRecord = Field(default_factory=TraceabilityRecord)
    message: str | None = None

    model_config = ConfigDict(from_attributes=True)
