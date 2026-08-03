import { buildAuthHeaders } from './authApi';
import { readApiError } from './apiErrors';
import type { AuthUser } from '../types/auth';
import type { GovernanceAuditRecord, RouterReviewSummaryResponse } from '../types/audit';
import type { DatabaseConnectionRecord } from '../types/databaseConnections';
import type { WorkspaceRecord } from '../types/workspace';
import type { MonitoringAlertRecord, MonitoringSummaryResponse } from '../types/monitoring';

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

export interface ActiveUserRecord {
  user_id: string;
  full_name: string;
  email: string;
  role: string;
  connected_at?: string | null;
  last_seen_at?: string | null;
  session_count?: number;
}

export async function listActiveUsers(): Promise<ActiveUserRecord[]> {
  const response = await fetch(`${getApiBaseUrl()}/admin/active-users`, {
    headers: { ...buildAuthHeaders() },
  });
  const data = await parseJson<{ active_users: ActiveUserRecord[] }>(response, 'Failed to load active users');
  return data.active_users || [];
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

export interface RouterReviewSummaryQuery {
  limit?: number;
  offset?: number;
  severity?: string;
  actor_user_id?: string;
  workspace_id?: string;
  connection_id?: string;
}

export async function getRouterReviewSummary(filters: RouterReviewSummaryQuery = {}): Promise<RouterReviewSummaryResponse> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 200));
  if (filters.offset) params.set('offset', String(filters.offset));
  if (filters.severity) params.set('severity', filters.severity);
  if (filters.actor_user_id) params.set('actor_user_id', filters.actor_user_id);
  if (filters.workspace_id) params.set('workspace_id', filters.workspace_id);
  if (filters.connection_id) params.set('connection_id', filters.connection_id);
  const response = await fetch(`${getApiBaseUrl()}/admin/router-summary?${params.toString()}`, {
    headers: { ...buildAuthHeaders() },
  });
  return parseJson<RouterReviewSummaryResponse>(response, 'Failed to load router review summary');
}

export async function getMonitoringSummary(): Promise<MonitoringSummaryResponse> {
  const response = await fetch(`${getApiBaseUrl()}/admin/monitoring/summary`, {
    headers: { ...buildAuthHeaders() },
  });
  return parseJson<MonitoringSummaryResponse>(response, 'Failed to load monitoring summary');
}

export interface MonitoringAlertQuery {
  limit?: number;
  offset?: number;
  status?: string;
  severity?: string;
  alert_type?: string;
  search?: string;
}

export async function listMonitoringAlerts(filters: MonitoringAlertQuery = {}): Promise<MonitoringAlertRecord[]> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 50));
  if (filters.offset) params.set('offset', String(filters.offset));
  if (filters.status) params.set('status', filters.status);
  if (filters.severity) params.set('severity', filters.severity);
  if (filters.alert_type) params.set('alert_type', filters.alert_type);
  if (filters.search) params.set('search', filters.search);
  const response = await fetch(`${getApiBaseUrl()}/admin/monitoring/alerts?${params.toString()}`, {
    headers: { ...buildAuthHeaders() },
  });
  const data = await parseJson<{ alerts: MonitoringAlertRecord[] }>(response, 'Failed to load monitoring alerts');
  return data.alerts || [];
}

export async function runMonitoringScan(): Promise<MonitoringSummaryResponse> {
  const response = await fetch(`${getApiBaseUrl()}/admin/monitoring/scan`, {
    method: 'POST',
    headers: { ...buildAuthHeaders() },
  });
  const data = await parseJson<{ success: boolean; summary: MonitoringSummaryResponse }>(response, 'Failed to run monitoring scan');
  return data.summary;
}

export async function updateMonitoringAlertStatus(alertId: string, status: string): Promise<MonitoringAlertRecord> {
  const response = await fetch(`${getApiBaseUrl()}/admin/monitoring/alerts/${alertId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ status }),
  });
  const data = await parseJson<{ success: boolean; alert: MonitoringAlertRecord }>(response, 'Failed to update monitoring alert');
  return data.alert;
}
