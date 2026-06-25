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


class CitationRecord(BaseModel):
    document_id: str | None = None
    file_name: str | None = None
    source_uri: str | None = None
    page_number: int | None = None
    section_title: str | None = None
    anchor_text: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    chunk_id: str | None = None
    citation_text: str | None = None
    relevance_score: float | None = None

    model_config = ConfigDict(from_attributes=True)


class AuditResponse(BaseModel):
    success: bool = True
    query: str
    intent: dict[str, Any] = Field(default_factory=dict)
    investigation_plan: dict[str, Any] = Field(default_factory=dict)
    entities_investigated: list[str] = Field(default_factory=list)
    entity_type: str | None = None
    entity_id: str | None = None
    agents_used: list[str] = Field(default_factory=list)
    risk_rating: str = "LOW"
    risk_score: int = 0
    risk_drivers: list[str] = Field(default_factory=list)
    document_intelligence_summary: str = ""
    document_intelligence: dict[str, Any] = Field(default_factory=dict)
    investigation_summary: str = ""
    investigation_metrics: dict[str, int] = Field(default_factory=dict)
    top_supporting_evidence: list[dict[str, Any]] = Field(default_factory=list)
    transaction_summary: str = ""
    vendor_summary: str = ""
    key_findings: list[str] = Field(default_factory=list)
    supporting_evidence: list[dict[str, Any]] = Field(default_factory=list)
    supporting_documents: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[CitationRecord] = Field(default_factory=list)
    navigation_payloads: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    structured_evidence: list[dict[str, Any]] = Field(default_factory=list)
    document_evidence: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    finding: dict[str, Any] = Field(default_factory=dict)
    final_response: str = ""
    traceability: TraceabilityRecord = Field(default_factory=TraceabilityRecord)
    message: str | None = None

    model_config = ConfigDict(from_attributes=True)
