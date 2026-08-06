import { readApiError } from './apiErrors';
import { buildAuthHeaders } from './authApi';
import type { KnowledgeGraphResponse, KnowledgeGraphEntityType } from '../types/audit';

function getApiBaseUrl(): string {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
  if (!apiBaseUrl) {
    throw new Error('VITE_API_BASE_URL is not configured.');
  }
  return apiBaseUrl.replace(/\/$/, '');
}

export async function fetchKnowledgeGraph(
  entityType: KnowledgeGraphEntityType,
  entityId: string,
  options: { refresh?: boolean; limit?: number } = {},
): Promise<KnowledgeGraphResponse> {
  const { refresh = true, limit = 25 } = options;
  const url = new URL(`${getApiBaseUrl()}/graph/entity/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}`);
  url.searchParams.set('refresh', String(refresh));
  url.searchParams.set('limit', String(limit));

  const response = await fetch(url.toString(), {
    headers: { ...buildAuthHeaders() },
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, 'Failed to load knowledge graph'));
  }

  const data: unknown = await response.json();
  if (!data || typeof data !== 'object') {
    throw new Error('Invalid knowledge graph response received from backend.');
  }

  const payload = data as Partial<KnowledgeGraphResponse>;
  if (typeof payload.success !== 'boolean') {
    throw new Error('Invalid knowledge graph response received from backend.');
  }
  if (!payload.success) {
    throw new Error(payload.message || 'Knowledge graph could not be loaded.');
  }

  return payload as KnowledgeGraphResponse;
}
