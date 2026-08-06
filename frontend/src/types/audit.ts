export interface TraceabilityRecord {
  agents_invoked: string[];
  agent_selection_reasoning: string[];
  sources_used: string[];
  evidence_used: Record<string, unknown>[];
  reasoning_path: string[];
  execution_metadata?: ExecutionMetadataRecord[];
  langfuse?: {
    enabled?: boolean;
    trace_id?: string | null;
    trace_url?: string | null;
    session_id?: string | null;
    name?: string | null;
    started_at?: string | null;
    ended_at?: string | null;
  };
}

export interface ExecutionMetadataRecord {
  agent?: string | null;
  reason_selected?: string | null;
  status?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
}

export interface DocumentSelectionExplanation {
  document_id?: string | null;
  selection_reason?: string | null;
  supports?: string | null;
  relevance_summary?: string | null;
  confidence_note?: string | null;
}

export interface CitationRecord {
  document_id?: string | null;
  file_name?: string | null;
  document_name?: string | null;
  source_uri?: string | null;
  source_type?: string | null;
  page_number?: number | null;
  section_title?: string | null;
  anchor_text?: string | null;
  start_offset?: number | null;
  end_offset?: number | null;
  chunk_id?: string | null;
  citation_text?: string | null;
  relevance_score?: number | null;
  linked_transaction?: string | null;
  related_vendor_id?: string | null;
  citation_origin?: string | null;
  selection_explanation?: DocumentSelectionExplanation | null;
  selection_reason?: string | null;
  supports?: string | null;
  relevance_summary?: string | null;
  confidence_note?: string | null;
}

export interface NavigationPayload {
  document_id?: string | null;
  file_name?: string | null;
  source_uri?: string | null;
  page_number?: number | null;
  section_title?: string | null;
  anchor_text?: string | null;
  start_offset?: number | null;
  end_offset?: number | null;
  chunk_id?: string | null;
  citation_text?: string | null;
}

export interface Finding {
  title?: string;
  summary?: string;
  category?: string;
  severity?: string;
  recommendation?: string;
  [key: string]: unknown;
}

export interface AuditResponse {
  success: boolean;
  query: string;
  intent: Record<string, unknown>;
  investigation_plan: Record<string, unknown>;
  entities_investigated: string[];
  entity_type: string | null;
  entity_id: string | null;
  agents_used: string[];
  risk_rating: string;
  risk_score: number;
  risk_drivers: string[];
  document_intelligence_summary: string;
  document_intelligence: Record<string, unknown>;
  investigation_summary: string;
  investigation_metrics: Record<string, number>;
  top_supporting_evidence: Record<string, unknown>[];
  transaction_summary: string;
  vendor_summary: string;
  key_findings: string[];
  supporting_evidence: Record<string, unknown>[];
  supporting_documents: Record<string, unknown>[];
  citations: CitationRecord[];
  navigation_payloads: NavigationPayload[];
  recommendations: string[];
  structured_evidence: Record<string, unknown>[];
  document_evidence: Record<string, unknown>[];
  sources: string[];
  reasoning: string[];
  finding: Finding;
  final_response: string;
  traceability: TraceabilityRecord;
  evaluation?: {
    retrieval_relevance?: string;
    grounding_quality?: string;
    faithfulness?: string;
    citation_coverage?: string;
    summary?: string;
  };
  execution_metadata?: ExecutionMetadataRecord[];
  message?: string | null;
}

export type KnowledgeGraphEntityType =
  | 'vendor'
  | 'transaction'
  | 'contract'
  | 'compliance_record'
  | 'audit_investigation'
  | 'document_metadata';

export interface KnowledgeGraphNodeRecord {
  node_id: string;
  entity_type: string;
  entity_id: string;
  display_label: string;
  node_kind: string;
  attributes: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface KnowledgeGraphEdgeRecord {
  edge_id: string;
  source_node_id: string;
  target_node_id: string;
  relationship_type: string;
  strength: number;
  metadata: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface KnowledgeGraphSummary {
  entity_type: string;
  entity_id: string;
  root_node_id?: string | null;
  node_count: number;
  edge_count: number;
  relationship_breakdown: Record<string, number>;
  generated_at?: string | null;
}

export interface KnowledgeGraphResponse {
  success: boolean;
  entity_type: string;
  entity_id: string;
  root_node?: KnowledgeGraphNodeRecord | null;
  nodes: KnowledgeGraphNodeRecord[];
  edges: KnowledgeGraphEdgeRecord[];
  summary: KnowledgeGraphSummary | Record<string, unknown>;
  message?: string | null;
}

// ── Chat / Conversation types ──────────────────────────────────────────────

export interface SuggestedAction {
  id: string;
  label: string;
  description: string;
}

export interface ChatSessionSummary {
  session_id: string;
  session_title: string;
  turn_count: number;
  workspace_id?: string | null;
  connection_id?: string | null;
  last_message_preview?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  last_message_at?: string | null;
  is_archived?: boolean;
}

export interface ChatTurnRecord {
  turn_id: string;
  turn_index: number;
  timestamp?: string | null;
  user_message: string;
  assistant_message: string;
  assistant_mode?: string;
  is_followup?: boolean;
  resolved_query?: string | null;
  response: ChatResponse;
}

export interface ChatHistoryResponse {
  session_id: string;
  session_title: string;
  turn_count: number;
  workspace_id?: string | null;
  connection_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  last_message_at?: string | null;
  turns: ChatTurnRecord[];
}

export interface InvestigationState {
  entity_type?: string | null;
  entity_ids: string[];
  transaction_ids: string[];
  topics: string[];
  risk_rating?: string | null;
  transaction_count: number;
  document_count: number;
  finding_count: number;
  key_findings: string[];
  recommendations: string[];
  status: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  response?: ChatResponse;
  isLoading?: boolean;
}

export interface ChatResponse extends AuditResponse {
  session_id: string;
  session_title?: string;
  is_followup: boolean;
  resolved_query: string;
  original_query: string;
  assistant_message?: string;
  conversation_mode?: string;
  injected_context: Record<string, unknown>;
  suggested_actions: SuggestedAction[];
  investigation_state: InvestigationState;
  turn_count: number;
}

export interface GovernanceAuditRecord {
  audit_log_id: string;
  actor_user_id?: string | null;
  actor_name?: string | null;
  action_type: string;
  entity_type: string;
  entity_id?: string | null;
  workspace_id?: string | null;
  connection_id?: string | null;
  severity: string;
  summary: string;
  before_state?: Record<string, unknown> | null;
  after_state?: Record<string, unknown> | null;
  created_at: string;
}

export interface GovernanceAuditListResponse {
  events: GovernanceAuditRecord[];
}

export interface RouterReviewItem {
  audit_log_id: string;
  created_at?: string | null;
  query?: string | null;
  selected_agent?: string | null;
  confidence?: number | null;
  escalate_to_planner?: boolean;
  decision_source?: string | null;
  candidate_agents?: string[];
  selected_agents?: string[];
  severity?: string | null;
  summary?: string | null;
}

export interface RouterReviewSummaryResponse {
  total_reviews: number;
  decision_events: number;
  path_review_events: number;
  escalated_count: number;
  low_confidence_count: number;
  path_mismatch_count: number;
  decision_source_counts: Record<string, number>;
  top_selected_agents: { agent: string; count: number }[];
  top_candidate_agents: { agent: string; count: number }[];
  recent_misroutes: RouterReviewItem[];
  recent_decisions: RouterReviewItem[];
  recent_path_reviews: RouterReviewItem[];
}
