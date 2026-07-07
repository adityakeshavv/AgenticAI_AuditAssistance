import type {
  DatabaseConnectionForm,
  DatabaseConnectionRecord,
  DatabaseConnectionSchemaInfo,
  DatabaseConnectionTableInfo,
} from '../types/databaseConnections';
import { buildAuthHeaders } from './authApi';

const ACTIVE_CONNECTION_KEY = 'audit_active_connection_id';

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

export function getSelectedDatabaseConnectionId(): string | null {
  return localStorage.getItem(ACTIVE_CONNECTION_KEY);
}

export function setSelectedDatabaseConnectionId(connectionId: string | null): void {
  if (!connectionId) {
    localStorage.removeItem(ACTIVE_CONNECTION_KEY);
    return;
  }
  localStorage.setItem(ACTIVE_CONNECTION_KEY, connectionId);
}

export async function listDatabaseConnections(): Promise<DatabaseConnectionRecord[]> {
  const response = await fetch(`${getApiBaseUrl()}/connections`, {
    headers: { ...buildAuthHeaders() },
  });
  const data = await parseJson<{ connections: DatabaseConnectionRecord[] }>(response, 'Failed to load database connections');
  return data.connections || [];
}

export async function testDatabaseConnection(payload: DatabaseConnectionForm): Promise<{
  success: boolean;
  message: string;
  schemas: DatabaseConnectionSchemaInfo[];
  tables: DatabaseConnectionTableInfo[];
}> {
  const response = await fetch(`${getApiBaseUrl()}/connections/test`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });
  return parseJson(response, 'Failed to test database connection');
}

export async function createDatabaseConnection(payload: DatabaseConnectionForm): Promise<{
  success: boolean;
  message?: string | null;
  connection: DatabaseConnectionRecord;
}> {
  const response = await fetch(`${getApiBaseUrl()}/connections`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });
  return parseJson(response, 'Failed to create database connection');
}

export async function activateDatabaseConnection(connectionId: string): Promise<DatabaseConnectionRecord> {
  const response = await fetch(`${getApiBaseUrl()}/connections/${connectionId}/activate`, {
    method: 'POST',
    headers: { ...buildAuthHeaders() },
  });
  const data = await parseJson<{ success: boolean; connection: DatabaseConnectionRecord }>(response, 'Failed to activate database connection');
  return data.connection;
}

export async function deleteDatabaseConnection(connectionId: string): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/connections/${connectionId}`, {
    method: 'DELETE',
    headers: { ...buildAuthHeaders() },
  });
  await parseJson(response, 'Failed to delete database connection');
}

export async function updateDatabaseConnectionSelection(
  connectionId: string,
  payload: { selected_schemas: string[]; selected_tables: string[]; is_default?: boolean | null },
): Promise<DatabaseConnectionRecord> {
  const response = await fetch(`${getApiBaseUrl()}/connections/${connectionId}/selection`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });
  const data = await parseJson<{ success: boolean; connection: DatabaseConnectionRecord }>(response, 'Failed to save database connection selection');
  return data.connection;
}

export async function getDatabaseConnection(connectionId: string): Promise<DatabaseConnectionRecord> {
  const response = await fetch(`${getApiBaseUrl()}/connections/${connectionId}`, {
    headers: { ...buildAuthHeaders() },
  });
  return parseJson(response, 'Failed to load database connection');
}

export async function getDatabaseConnectionSchemas(connectionId: string): Promise<DatabaseConnectionSchemaInfo[]> {
  const response = await fetch(`${getApiBaseUrl()}/connections/${connectionId}/schemas`, {
    headers: { ...buildAuthHeaders() },
  });
  return parseJson(response, 'Failed to load schemas');
}

export async function getDatabaseConnectionTables(connectionId: string, schemaName?: string): Promise<DatabaseConnectionTableInfo[]> {
  const url = new URL(`${getApiBaseUrl()}/connections/${connectionId}/tables`);
  if (schemaName) {
    url.searchParams.set('schema_name', schemaName);
  }
  const response = await fetch(url.toString(), {
    headers: { ...buildAuthHeaders() },
  });
  return parseJson(response, 'Failed to load tables');
}
