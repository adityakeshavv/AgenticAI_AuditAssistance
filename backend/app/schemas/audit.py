from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditQueryRequest(BaseModel):
    query: str
    page: int = 1
    page_size: int = 10
    connection_id: str | None = None
    workspace_id: str | None = None


class TraceabilityRecord(BaseModel):
    agents_invoked: list[str] = Field(default_factory=list)
    agent_selection_reasoning: list[str] = Field(default_factory=list)
    sources_used: list[str] = Field(default_factory=list)
    evidence_used: list[dict[str, Any]] = Field(default_factory=list)
    reasoning_path: list[str] = Field(default_factory=list)
    execution_metadata: list[dict[str, Any]] = Field(default_factory=list)
    langfuse: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class DocumentSelectionExplanation(BaseModel):
    document_id: str | None = None
    selection_reason: str | None = None
    supports: str | None = None
    relevance_summary: str | None = None
    confidence_note: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CitationRecord(BaseModel):
    document_id: str | None = None
    file_name: str | None = None
    document_name: str | None = None
    source_uri: str | None = None
    source_type: str | None = None
    page_number: int | None = None
    section_title: str | None = None
    anchor_text: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    chunk_id: str | None = None
    citation_text: str | None = None
    relevance_score: float | None = None
    linked_transaction: str | None = None
    related_vendor_id: str | None = None
    citation_origin: str | None = None
    selection_explanation: DocumentSelectionExplanation | None = None
    selection_reason: str | None = None
    supports: str | None = None
    relevance_summary: str | None = None
    confidence_note: str | None = None

    model_config = ConfigDict(from_attributes=True)


class NavigationPayload(BaseModel):
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

    model_config = ConfigDict(from_attributes=True)


class EvaluationRecord(BaseModel):
    retrieval_relevance: str | None = None
    grounding_quality: str | None = None
    faithfulness: str | None = None
    citation_coverage: str | None = None
    summary: str | None = None

    model_config = ConfigDict(from_attributes=True)


class WorkpaperRecord(BaseModel):
    workpaper_id: str | None = None
    title: str | None = None
    generated_at: str | None = None
    query: str | None = None
    objective: str | None = None
    scope: dict[str, Any] = Field(default_factory=dict)
    methodology: list[str] = Field(default_factory=list)
    summary: str | None = None
    finding: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    risk_assessment: dict[str, Any] = Field(default_factory=dict)
    key_findings: list[str] = Field(default_factory=list)
    supporting_evidence: list[dict[str, Any]] = Field(default_factory=list)
    supporting_documents: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[CitationRecord] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    validation: EvaluationRecord | dict[str, Any] | None = None
    traceability: TraceabilityRecord | dict[str, Any] = Field(default_factory=dict)
    execution_metadata: list[ExecutionMetadataRecord] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ReportExportRecord(BaseModel):
    formats: list[str] = Field(default_factory=list)
    file_name: str | None = None
    markdown: str | None = None
    json: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class WorkflowStageRecord(BaseModel):
    name: str | None = None
    label: str | None = None
    status: str | None = None
    description: str | None = None
    summary: str | None = None

    model_config = ConfigDict(from_attributes=True)


class WorkflowAutomationRecord(BaseModel):
    workflow_id: str | None = None
    workflow_type: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    current_stage: str | None = None
    overall_status: str | None = None
    progress: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    stages: list[WorkflowStageRecord] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ExecutionMetadataRecord(BaseModel):
    agent: str | None = None
    reason_selected: str | None = None
    status: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class RouterReviewItem(BaseModel):
    audit_log_id: str
    created_at: str | None = None
    query: str | None = None
    selected_agent: str | None = None
    confidence: float | None = None
    escalate_to_planner: bool = False
    decision_source: str | None = None
    candidate_agents: list[str] = Field(default_factory=list)
    selected_agents: list[str] = Field(default_factory=list)
    severity: str | None = None
    summary: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RouterReviewSummaryResponse(BaseModel):
    total_reviews: int = 0
    decision_events: int = 0
    path_review_events: int = 0
    escalated_count: int = 0
    low_confidence_count: int = 0
    path_mismatch_count: int = 0
    decision_source_counts: dict[str, int] = Field(default_factory=dict)
    top_selected_agents: list[dict[str, Any]] = Field(default_factory=list)
    top_candidate_agents: list[dict[str, Any]] = Field(default_factory=list)
    recent_misroutes: list[RouterReviewItem] = Field(default_factory=list)
    recent_decisions: list[RouterReviewItem] = Field(default_factory=list)
    recent_path_reviews: list[RouterReviewItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AuditResponse(BaseModel):
    success: bool = True
    query: str
    intent: dict[str, Any] = Field(default_factory=dict)
    routing_decision: dict[str, Any] = Field(default_factory=dict)
    source_route: dict[str, Any] = Field(default_factory=dict)
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
    navigation_payloads: list[NavigationPayload] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    structured_evidence: list[dict[str, Any]] = Field(default_factory=list)
    document_evidence: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    finding: dict[str, Any] = Field(default_factory=dict)
    final_response: str = ""
    traceability: TraceabilityRecord = Field(default_factory=TraceabilityRecord)
    evaluation: EvaluationRecord | None = None
    workflow_automation: WorkflowAutomationRecord | dict[str, Any] | None = None
    workpaper: WorkpaperRecord | None = None
    report_exports: ReportExportRecord | None = None
    execution_metadata: list[ExecutionMetadataRecord] = Field(default_factory=list)
    message: str | None = None

    model_config = ConfigDict(from_attributes=True)
