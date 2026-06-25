export interface TraceabilityRecord {
  agents_invoked: string[];
  agent_selection_reasoning: string[];
  sources_used: string[];
  evidence_used: Record<string, unknown>[];
  reasoning_path: string[];
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
  message?: string | null;
}
