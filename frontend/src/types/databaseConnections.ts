export interface DatabaseConnectionRecord {
  connection_id: string;
  connection_name: string;
  database_type: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  is_default: boolean;
  is_active: boolean;
  selected_schemas: string[];
  selected_tables: string[];
  last_test_status?: string | null;
  last_test_message?: string | null;
  last_tested_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DatabaseConnectionSchemaInfo {
  schema_name: string;
  tables: string[];
  table_count: number;
}

export interface DatabaseConnectionTableInfo {
  table_name: string;
  schema_name: string;
  columns: string[];
  column_count: number;
}

export interface DatabaseTableColumnInfo {
  name: string;
  data_type?: string | null;
  nullable?: boolean | null;
  default?: string | null;
}

export interface DatabaseConnectionTableDetailInfo extends DatabaseConnectionTableInfo {
  summary: string;
  row_count: number;
  primary_key_columns: string[];
  column_details: DatabaseTableColumnInfo[];
  sample_rows: Record<string, unknown>[];
}

export interface DatabaseConnectionForm {
  connection_name: string;
  database_type: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  password: string;
  selected_schemas: string[];
  selected_tables: string[];
}

export interface DocumentUploadForm {
  file: File;
  document_type?: string;
  document_category?: string;
  related_vendor_id?: string;
  related_employee_id?: string;
  related_transaction_id?: string;
  related_contract_id?: string;
  related_investigation_id?: string;
}

export interface DocumentUploadProcessingRecord {
  supported?: boolean;
  file_type?: string;
  content_snippet?: string;
  content_length?: number;
  processing_summary?: string;
  signals?: string[];
  risk_contribution?: string[];
  document_intelligence?: Record<string, unknown>;
}

export interface DocumentUploadResponse {
  success: boolean;
  message: string;
  document: Record<string, unknown>;
  processing?: DocumentUploadProcessingRecord;
}

export interface DocumentMetadataRecord {
  document_id: string;
  document_type: string;
  document_category: string;
  related_vendor_id?: string | null;
  related_employee_id?: string | null;
  related_transaction_id?: string | null;
  related_contract_id?: string | null;
  related_investigation_id?: string | null;
  creation_date: string;
  file_name: string;
  file_path: string;
  source_uri: string;
  source_metadata_file: string;
  created_at?: string | null;
  updated_at?: string | null;
}
