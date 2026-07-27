import type {
  DatabaseConnectionForm,
  DatabaseConnectionRecord,
  DocumentMetadataRecord,
  DocumentUploadResponse,
  DatabaseConnectionTableDetailInfo,
  DatabaseConnectionSchemaInfo,
  DatabaseConnectionTableInfo,
  DocumentUploadForm,
} from '../types/databaseConnections';
import { readApiError } from './apiErrors';
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
    throw new Error(await readApiError(response, message));
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

export async function getDatabaseConnectionTableDetail(
  connectionId: string,
  schemaName: string,
  tableName: string,
): Promise<DatabaseConnectionTableDetailInfo> {
  const response = await fetch(
    `${getApiBaseUrl()}/connections/${connectionId}/tables/${encodeURIComponent(schemaName)}/${encodeURIComponent(tableName)}`,
    {
      headers: { ...buildAuthHeaders() },
    },
  );
  return parseJson(response, 'Failed to load table details');
}

export async function uploadDocumentSource(payload: DocumentUploadForm): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append('file', payload.file);
  if (payload.document_type) formData.append('document_type', payload.document_type);
  if (payload.document_category) formData.append('document_category', payload.document_category);
  if (payload.related_vendor_id) formData.append('related_vendor_id', payload.related_vendor_id);
  if (payload.related_employee_id) formData.append('related_employee_id', payload.related_employee_id);
  if (payload.related_transaction_id) formData.append('related_transaction_id', payload.related_transaction_id);
  if (payload.related_contract_id) formData.append('related_contract_id', payload.related_contract_id);
  if (payload.related_investigation_id) formData.append('related_investigation_id', payload.related_investigation_id);

  const response = await fetch(`${getApiBaseUrl()}/connections/documents/upload`, {
    method: 'POST',
    headers: { ...buildAuthHeaders() },
    body: formData,
  });
  return parseJson(response, 'Failed to upload document');
}

export async function listUploadedDocuments(filters: {
  search?: string;
  document_type?: string;
  document_category?: string;
  related_vendor_id?: string;
  related_employee_id?: string;
  related_transaction_id?: string;
  related_contract_id?: string;
  related_investigation_id?: string;
  uploaded_only?: boolean;
} = {}): Promise<DocumentMetadataRecord[]> {
  const url = new URL(`${getApiBaseUrl()}/connections/documents`);
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value));
    }
  });
  const response = await fetch(url.toString(), {
    headers: { ...buildAuthHeaders() },
  });
  const data = await parseJson<{ documents: DocumentMetadataRecord[] }>(response, 'Failed to load uploaded documents');
  return data.documents || [];
}
