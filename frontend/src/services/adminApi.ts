import { buildAuthHeaders } from './authApi';
import { readApiError } from './apiErrors';
import type { AuthUser } from '../types/auth';
import type { GovernanceAuditRecord } from '../types/audit';
import type { DatabaseConnectionRecord } from '../types/databaseConnections';
import type { WorkspaceRecord } from '../types/workspace';

function getApiBaseUrl(): string {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
  if (!apiBaseUrl) {
    throw new Error('VITE_API_BASE_URL is not configured.');
  }
  return apiBaseUrl.replace(/\/$/, '');
}

async function parseJson<T>(response: Response, message: string): Promise<T> {
  if (!response.ok) {
    throw new Error(await readApiError(response, message));
  }
  return response.json() as Promise<T>;
}

export async function listAdminUsers(): Promise<AuthUser[]> {
  const response = await fetch(`${getApiBaseUrl()}/admin/users`, {
    headers: { ...buildAuthHeaders() },
  });
  const data = await parseJson<{ users: AuthUser[] }>(response, 'Failed to load admin users');
  return data.users || [];
}

export async function listAdminWorkspaces(): Promise<WorkspaceRecord[]> {
  const response = await fetch(`${getApiBaseUrl()}/admin/workspaces`, {
    headers: { ...buildAuthHeaders() },
  });
  const data = await parseJson<{ workspaces: WorkspaceRecord[] }>(response, 'Failed to load admin workspaces');
  return data.workspaces || [];
}

export async function listAdminConnections(): Promise<DatabaseConnectionRecord[]> {
  const response = await fetch(`${getApiBaseUrl()}/admin/connections`, {
    headers: { ...buildAuthHeaders() },
  });
  const data = await parseJson<{ connections: DatabaseConnectionRecord[] }>(response, 'Failed to load admin sources');
  return data.connections || [];
}

export async function updateAdminUserStatus(userId: string, isActive: boolean): Promise<AuthUser> {
  const response = await fetch(`${getApiBaseUrl()}/admin/users/${userId}/status`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ is_active: isActive }),
  });
  const data = await parseJson<{ success: boolean; user: AuthUser }>(response, 'Failed to update user status');
  return data.user;
}

export async function listGovernanceAuditEvents(limit = 25): Promise<GovernanceAuditRecord[]> {
  const response = await fetch(`${getApiBaseUrl()}/admin/audit-events?limit=${encodeURIComponent(String(limit))}`, {
    headers: { ...buildAuthHeaders() },
  });
  const data = await parseJson<{ events: GovernanceAuditRecord[] }>(response, 'Failed to load governance activity');
  return data.events || [];
}

export interface GovernanceAuditQuery {
  limit?: number;
  offset?: number;
  action_type?: string;
  entity_type?: string;
  severity?: string;
  actor_user_id?: string;
  search?: string;
  entity_id?: string;
  workspace_id?: string;
  connection_id?: string;
}

export async function listGovernanceAuditEventsWithFilters(filters: GovernanceAuditQuery = {}): Promise<GovernanceAuditRecord[]> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 25));
  if (filters.offset) params.set('offset', String(filters.offset));
  if (filters.action_type) params.set('action_type', filters.action_type);
  if (filters.entity_type) params.set('entity_type', filters.entity_type);
  if (filters.severity) params.set('severity', filters.severity);
  if (filters.actor_user_id) params.set('actor_user_id', filters.actor_user_id);
  if (filters.search) params.set('search', filters.search);
  if (filters.entity_id) params.set('entity_id', filters.entity_id);
  if (filters.workspace_id) params.set('workspace_id', filters.workspace_id);
  if (filters.connection_id) params.set('connection_id', filters.connection_id);
  const response = await fetch(`${getApiBaseUrl()}/admin/audit-events?${params.toString()}`, {
    headers: { ...buildAuthHeaders() },
  });
  const data = await parseJson<{ events: GovernanceAuditRecord[] }>(response, 'Failed to load governance activity');
  return data.events || [];
}
