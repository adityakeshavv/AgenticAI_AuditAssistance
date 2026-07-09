export interface WorkspaceRecord {
  workspace_id: string;
  workspace_name: string;
  description?: string | null;
  selected_connection_ids: string[];
  active_connection_id?: string | null;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceForm {
  workspace_name: string;
  description: string;
  selected_connection_ids: string[];
  active_connection_id: string;
}

