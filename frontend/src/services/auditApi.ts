import type { AuditResponse } from '../types/audit';
import { readApiError } from './apiErrors';
import { buildAuthHeaders } from './authApi';
import { getSelectedDatabaseConnectionId } from './databaseConnectionsApi';
import { getSelectedWorkspaceId } from './workspacesApi';

export async function submitAuditQuery(query: string): Promise<AuditResponse> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
  if (!apiBaseUrl) {
    throw new Error('VITE_API_BASE_URL is not configured.');
  }

  const response = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/audit/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({
      query,
      page: 1,
      page_size: 10,
      connection_id: getSelectedDatabaseConnectionId(),
      workspace_id: getSelectedWorkspaceId(),
    }),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, 'Failed to run audit query'));
  }

  const data: unknown = await response.json();
  return validateAuditResponse(data);
}

function validateAuditResponse(data: unknown): AuditResponse {
  if (!data || typeof data !== 'object') {
    throw new Error('Invalid response shape received from backend.');
  }

  const response = data as Partial<AuditResponse>;
  if (typeof response.success !== 'boolean' || typeof response.query !== 'string' || !Array.isArray(response.citations)) {
    throw new Error('Invalid response shape received from backend.');
  }

  return response as AuditResponse;
}

// ── Chat API ───────────────────────────────────────────────────────────────

import type { ChatResponse } from '../types/audit';

export async function sendChatMessage(
  message: string,
  sessionId: string | null,
): Promise<ChatResponse> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
  if (!apiBaseUrl) throw new Error('VITE_API_BASE_URL is not configured.');

  const response = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/chat/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...buildAuthHeaders() },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      page: 1,
      page_size: 10,
      connection_id: getSelectedDatabaseConnectionId(),
      workspace_id: getSelectedWorkspaceId(),
    }),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, 'Failed to send chat message'));
  }

  const data = await response.json();
  return data as ChatResponse;
}

export async function createChatSession(): Promise<string> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
  if (!apiBaseUrl) throw new Error('VITE_API_BASE_URL is not configured.');
  const response = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/chat/session`, {
    method: 'POST',
    headers: {
      ...buildAuthHeaders(),
    },
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, 'Failed to create chat session'));
  }
  const data = await response.json();
  return data.session_id as string;
}

export async function getChatHistory(sessionId: string): Promise<unknown> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
  if (!apiBaseUrl) throw new Error('VITE_API_BASE_URL is not configured.');
  const response = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/chat/session/${sessionId}/history`, {
    headers: {
      ...buildAuthHeaders(),
    },
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, 'Failed to load chat history'));
  }
  return response.json();
}
