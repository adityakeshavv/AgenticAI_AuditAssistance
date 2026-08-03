export type WorkspaceCollaborationItemType = 'comment' | 'task' | 'review' | string;

export interface WorkspaceCollaborationItem {
  collaboration_id: string;
  workspace_id: string;
  item_type: WorkspaceCollaborationItemType;
  title?: string | null;
  body?: string | null;
  status?: string | null;
  priority?: string | null;
  mentions: string[];
  assignee_user_id?: string | null;
  created_by_user_id?: string | null;
  due_date?: string | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceCollaborationSummary {
  total_items: number;
  open_items: number;
  completed_items: number;
  comment_count: number;
  task_count: number;
  review_count: number;
  mention_count: number;
}

export interface WorkspaceCollaborationListResponse {
  items: WorkspaceCollaborationItem[];
  summary: WorkspaceCollaborationSummary;
}

export interface WorkspaceCollaborationCreatePayload {
  item_type: WorkspaceCollaborationItemType;
  title?: string | null;
  body?: string | null;
  status?: string | null;
  priority?: string | null;
  mentions?: string[];
  assignee_user_id?: string | null;
  due_date?: string | null;
}

export interface WorkspaceCollaborationUpdatePayload {
  title?: string | null;
  body?: string | null;
  status?: string | null;
  priority?: string | null;
  mentions?: string[];
  assignee_user_id?: string | null;
  due_date?: string | null;
}
