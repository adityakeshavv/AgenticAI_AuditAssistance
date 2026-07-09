import type { WorkspaceForm, WorkspaceRecord } from '../types/workspace';
import { buildAuthHeaders } from './authApi';

const ACTIVE_WORKSPACE_KEY = 'audit_active_workspace_id';
const ACTIVE_WORKSPACE_CONNECTION_KEY = 'audit_active_workspace_connection_id';

function getApiBaseUrl(): string {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
  if (!apiBaseUrl) {
    throw new Error('VITE_API_BASE_URL is not configured.');
  }
  return apiBaseUrl.replace(/\/$/, '');
}

async function parseJson<T>(response: Response, message: string): Promise<T> {
  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    throw new Error(errorText || `${message} (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function getSelectedWorkspaceId(): string | null {
  return localStorage.getItem(ACTIVE_WORKSPACE_KEY);
}

export function setSelectedWorkspaceId(workspaceId: string | null): void {
  if (!workspaceId) {
    localStorage.removeItem(ACTIVE_WORKSPACE_KEY);
    return;
  }
  localStorage.setItem(ACTIVE_WORKSPACE_KEY, workspaceId);
}

export function getSelectedWorkspaceConnectionId(): string | null {
  return localStorage.getItem(ACTIVE_WORKSPACE_CONNECTION_KEY);
}

export function setSelectedWorkspaceConnectionId(connectionId: string | null): void {
  if (!connectionId) {
    localStorage.removeItem(ACTIVE_WORKSPACE_CONNECTION_KEY);
    return;
  }
  localStorage.setItem(ACTIVE_WORKSPACE_CONNECTION_KEY, connectionId);
}

export async function listWorkspaces(): Promise<WorkspaceRecord[]> {
  const response = await fetch(`${getApiBaseUrl()}/workspaces`, {
    headers: { ...buildAuthHeaders() },
  });
  const data = await parseJson<{ workspaces: WorkspaceRecord[] }>(response, 'Failed to load workspaces');
  return data.workspaces || [];
}

export async function createWorkspace(payload: WorkspaceForm): Promise<{ success: boolean; message?: string | null; workspace: WorkspaceRecord }> {
  const response = await fetch(`${getApiBaseUrl()}/workspaces`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });
  return parseJson(response, 'Failed to create workspace');
}

export async function updateWorkspaceSelection(
  workspaceId: string,
  payload: { selected_connection_ids: string[]; active_connection_id?: string | null; is_default?: boolean | null },
): Promise<WorkspaceRecord> {
  const response = await fetch(`${getApiBaseUrl()}/workspaces/${workspaceId}/selection`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });
  const data = await parseJson<{ success: boolean; workspace: WorkspaceRecord }>(response, 'Failed to save workspace selection');
  return data.workspace;
}

export async function activateWorkspace(workspaceId: string): Promise<WorkspaceRecord> {
  const response = await fetch(`${getApiBaseUrl()}/workspaces/${workspaceId}/activate`, {
    method: 'POST',
    headers: { ...buildAuthHeaders() },
  });
  const data = await parseJson<{ success: boolean; workspace: WorkspaceRecord }>(response, 'Failed to activate workspace');
  return data.workspace;
}

export async function deleteWorkspace(workspaceId: string): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/workspaces/${workspaceId}`, {
    method: 'DELETE',
    headers: { ...buildAuthHeaders() },
  });
  await parseJson(response, 'Failed to delete workspace');
}

