import { getStoredAuthToken } from './authApi';

export interface RealtimeSocketEvent {
  type?: string;
  action_type?: string;
  entity_type?: string;
  entity_id?: string | null;
  workspace_id?: string | null;
  connection_id?: string | null;
  severity?: string | null;
  summary?: string | null;
  created_at?: string | null;
  [key: string]: unknown;
}

function getApiBaseUrl(): string {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
  if (!apiBaseUrl) {
    throw new Error('VITE_API_BASE_URL is not configured.');
  }
  return apiBaseUrl.replace(/\/$/, '');
}

function buildRealtimeUrl(token: string): string {
  const wsUrl = new URL('/ws/updates', getApiBaseUrl());
  wsUrl.protocol = wsUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  wsUrl.searchParams.set('token', token);
  return wsUrl.toString();
}

export function connectRealtimeSocket(
  onEvent: (event: RealtimeSocketEvent) => void,
  onStatusChange?: (connected: boolean) => void,
): WebSocket | null {
  const token = getStoredAuthToken();
  if (!token) {
    return null;
  }

  const socket = new WebSocket(buildRealtimeUrl(token));
  socket.onopen = () => onStatusChange?.(true);
  socket.onclose = () => onStatusChange?.(false);
  socket.onerror = () => onStatusChange?.(false);
  socket.onmessage = (message) => {
    try {
      const parsed = JSON.parse(message.data as string) as RealtimeSocketEvent;
      onEvent(parsed);
    } catch {
      onEvent({ type: 'realtime_raw', summary: String(message.data) });
    }
  };
  return socket;
}
