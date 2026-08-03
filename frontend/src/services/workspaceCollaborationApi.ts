import { readApiError } from './apiErrors';
import { buildAuthHeaders } from './authApi';
import type {
  WorkspaceCollaborationCreatePayload,
  WorkspaceCollaborationItem,
  WorkspaceCollaborationListResponse,
  WorkspaceCollaborationUpdatePayload,
} from '../types/workspaceCollaboration';

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

export async function listWorkspaceCollaborationItems(workspaceId: string, itemType?: string | null): Promise<WorkspaceCollaborationListResponse> {
  const params = new URLSearchParams();
  if (itemType) {
    params.set('item_type', itemType);
  }
  const query = params.toString();
  const response = await fetch(`${getApiBaseUrl()}/workspaces/${workspaceId}/collaboration${query ? `?${query}` : ''}`, {
    headers: { ...buildAuthHeaders() },
  });
  return parseJson(response, 'Failed to load collaboration items');
}

export async function createWorkspaceCollaborationItem(
  workspaceId: string,
  payload: WorkspaceCollaborationCreatePayload,
): Promise<WorkspaceCollaborationItem> {
  const response = await fetch(`${getApiBaseUrl()}/workspaces/${workspaceId}/collaboration`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });
  return parseJson(response, 'Failed to save collaboration item');
}

export async function updateWorkspaceCollaborationItem(
  workspaceId: string,
  collaborationId: string,
  payload: WorkspaceCollaborationUpdatePayload,
): Promise<WorkspaceCollaborationItem> {
  const response = await fetch(`${getApiBaseUrl()}/workspaces/${workspaceId}/collaboration/${collaborationId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });
  return parseJson(response, 'Failed to update collaboration item');
}

export async function deleteWorkspaceCollaborationItem(workspaceId: string, collaborationId: string): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/workspaces/${workspaceId}/collaboration/${collaborationId}`, {
    method: 'DELETE',
    headers: { ...buildAuthHeaders() },
  });
  await parseJson(response, 'Failed to delete collaboration item');
}
