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
