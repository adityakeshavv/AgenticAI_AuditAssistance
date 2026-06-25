import type { AuditResponse } from '../types/audit';

export async function submitAuditQuery(query: string): Promise<AuditResponse> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
  if (!apiBaseUrl) {
    throw new Error('VITE_API_BASE_URL is not configured.');
  }

  const response = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/audit/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      page: 1,
      page_size: 10,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    throw new Error(errorText || `Request failed with status ${response.status}`);
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
