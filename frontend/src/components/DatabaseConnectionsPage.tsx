import { useEffect, useMemo, useState } from 'react';
import {
  activateDatabaseConnection,
  createDatabaseConnection,
  deleteDatabaseConnection,
  getDatabaseConnection,
  getDatabaseConnectionTableDetail,
  getDatabaseConnectionSchemas,
  getDatabaseConnectionTables,
  getSelectedDatabaseConnectionId,
  listDatabaseConnections,
  listUploadedDocuments,
  setSelectedDatabaseConnectionId,
  updateDatabaseConnectionSelection,
  uploadDocumentSource,
  testDatabaseConnection,
} from '../services/databaseConnectionsApi';
import { FeedbackBanner } from './FeedbackBanner';
import type {
  DatabaseConnectionForm,
  DatabaseConnectionRecord,
  DatabaseConnectionTableDetailInfo,
  DatabaseConnectionSchemaInfo,
  DatabaseConnectionTableInfo,
  DocumentMetadataRecord,
  DocumentUploadProcessingRecord,
  DocumentUploadForm,
} from '../types/databaseConnections';

const DEFAULT_FORM: DatabaseConnectionForm = {
  connection_name: '',
  database_type: 'postgresql',
  host: 'localhost',
  port: 5432,
  database_name: '',
  username: '',
  password: '',
  selected_schemas: [],
  selected_tables: [],
};

const DATABASE_TYPE_OPTIONS = [{ value: 'postgresql', label: 'PostgreSQL' }];
const DOCUMENT_TYPE_OPTIONS = [
  { value: 'pdf', label: 'PDF' },
  { value: 'docx', label: 'DOCX' },
  { value: 'txt', label: 'TXT' },
  { value: 'eml', label: 'EML' },
];
const DOCUMENT_CATEGORY_OPTIONS = [
  { value: 'supporting_document', label: 'Supporting Document' },
  { value: 'audit_report', label: 'Audit Report' },
  { value: 'investigation_report', label: 'Investigation Report' },
  { value: 'policy', label: 'Policy' },
  { value: 'sop', label: 'SOP' },
  { value: 'email', label: 'Email' },
  { value: 'meeting_minutes', label: 'Meeting Minutes' },
  { value: 'contract', label: 'Contract' },
];

function prettyDate(value?: string | null) {
  if (!value) return 'n/a';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function cleanConnectionTestMessage(message: string, success: boolean): string {
  const trimmed = message.trim();
  if (success) {
    return trimmed || 'Connection check passed.';
  }

  const collapsed = trimmed
    .replace(/\s+/g, ' ')
    .replace(/\(Background on this error.*$/i, '')
    .replace(/Multiple connection attempts failed.*$/i, '')
    .replace(/- host:.*$/i, '')
    .replace(/^\(psycopg[^)]*\)\s*/i, '')
    .trim()
    .replace(/[.:-]+$/, '');

  if (/password authentication failed/i.test(collapsed)) {
    return 'Connection failed: password authentication failed for the supplied username.';
  }
  if (/database .* does not exist/i.test(collapsed)) {
    return 'Connection failed: the selected database does not exist.';
  }
  if (collapsed) {
    return `Connection failed: ${collapsed}`;
  }
  return 'Connection failed. Please verify the host, port, database name, username, and password.';
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="card-sm">
      <p className="label" style={{ marginBottom: '0.25rem' }}>{label}</p>
      <p className="small-copy" style={{ wordBreak: 'break-word' }}>{value}</p>
    </div>
  );
}

type DatabaseConnectionsPageProps = {
  isAdminView?: boolean;
  realtimeTick?: number;
};

type DocumentUploadDraft = {
  file: File | null;
  document_type: string;
  document_category: string;
  related_vendor_id: string;
  related_employee_id: string;
  related_transaction_id: string;
  related_contract_id: string;
  related_investigation_id: string;
};

const DEFAULT_UPLOAD_DRAFT: DocumentUploadDraft = {
  file: null,
  document_type: 'pdf',
  document_category: 'supporting_document',
  related_vendor_id: '',
  related_employee_id: '',
  related_transaction_id: '',
  related_contract_id: '',
  related_investigation_id: '',
};

export function DatabaseConnectionsPage({ isAdminView = false, realtimeTick = 0 }: DatabaseConnectionsPageProps) {
  const [connections, setConnections] = useState<DatabaseConnectionRecord[]>([]);
  const [selectedConnectionId, setSelectedConnectionIdState] = useState<string | null>(getSelectedDatabaseConnectionId());
  const [selectedConnection, setSelectedConnection] = useState<DatabaseConnectionRecord | null>(null);
  const [schemas, setSchemas] = useState<DatabaseConnectionSchemaInfo[]>([]);
  const [tables, setTables] = useState<DatabaseConnectionTableInfo[]>([]);
  const [selectedSchemas, setSelectedSchemas] = useState<string[]>([]);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [selectedTableDetail, setSelectedTableDetail] = useState<DatabaseConnectionTableDetailInfo | null>(null);
  const [isTablePreviewOpen, setIsTablePreviewOpen] = useState(false);
  const [tableDetailLoading, setTableDetailLoading] = useState(false);
  const [tableDetailError, setTableDetailError] = useState<string | null>(null);
  const [uploadDraft, setUploadDraft] = useState<DocumentUploadDraft>(DEFAULT_UPLOAD_DRAFT);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [uploadProcessing, setUploadProcessing] = useState<DocumentUploadProcessingRecord | null>(null);
  const [documentRefreshTick, setDocumentRefreshTick] = useState(0);
  const [documentSearch, setDocumentSearch] = useState('');
  const [documentTypeFilter, setDocumentTypeFilter] = useState('');
  const [documentCategoryFilter, setDocumentCategoryFilter] = useState('');
  const [documentEntityFilter, setDocumentEntityFilter] = useState('');
  const [uploadedDocuments, setUploadedDocuments] = useState<DocumentMetadataRecord[]>([]);
  const [uploadedDocumentsLoading, setUploadedDocumentsLoading] = useState(false);
  const [uploadedDocumentsError, setUploadedDocumentsError] = useState<string | null>(null);
  const [selectedUploadedDocumentId, setSelectedUploadedDocumentId] = useState<string | null>(null);
  const [isDocumentDetailOpen, setIsDocumentDetailOpen] = useState(false);
  const [form, setForm] = useState<DatabaseConnectionForm>(DEFAULT_FORM);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testMessage, setTestMessage] = useState<string | null>(null);

  const activeConnection = useMemo(
    () => connections.find((item) => item.connection_id === selectedConnectionId) || null,
    [connections, selectedConnectionId],
  );

  const sourceJourney = [
    {
      label: 'Test Connection',
      detail: 'Verify host, credentials, and database reachability before saving.',
      complete: Boolean(activeConnection?.last_test_status === 'success' || activeConnection?.last_test_status === 'passed'),
    },
    {
      label: 'Save Source',
      detail: 'Store the connection securely for reuse in the workspace.',
      complete: Boolean(activeConnection?.connection_id),
    },
    {
      label: 'Select Schema & Tables',
      detail: 'Choose the data that the audit assistant should query.',
      complete: Boolean(selectedSchemas.length || selectedTables.length),
    },
    {
      label: 'Upload Documents',
      detail: 'Add supporting PDFs, docs, emails, or text files to enrich evidence.',
      complete: Boolean(uploadMessage),
    },
  ];
  const loadConnections = async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await listDatabaseConnections();
      setConnections(items);
      if (!selectedConnectionId && items.length > 0) {
        const defaultConnection = items.find((item) => item.is_default) || items[0];
        if (defaultConnection) {
          setSelectedConnectionIdState(defaultConnection.connection_id);
          setSelectedDatabaseConnectionId(defaultConnection.connection_id);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load database connections.');
    } finally {
      setLoading(false);
    }
  };

  const loadConnectionDetail = async (connectionId: string) => {
    try {
      const detail = await getDatabaseConnection(connectionId);
      setSelectedConnection(detail);
      setSelectedSchemas(detail.selected_schemas || []);
      setSelectedTables(detail.selected_tables || []);
      setSelectedTableDetail(null);
      setIsTablePreviewOpen(false);
      setTableDetailError(null);
      setSchemas(await getDatabaseConnectionSchemas(connectionId));
      setTables(await getDatabaseConnectionTables(connectionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load connection details.');
    }
  };

  useEffect(() => {
    void loadConnections();
  }, [realtimeTick]);

  useEffect(() => {
    if (selectedConnectionId) {
      setSelectedDatabaseConnectionId(selectedConnectionId);
      void loadConnectionDetail(selectedConnectionId);
    } else {
      setSelectedConnection(null);
      setSchemas([]);
      setTables([]);
      setSelectedSchemas([]);
      setSelectedTables([]);
    }
  }, [selectedConnectionId, realtimeTick]);

  useEffect(() => {
    let cancelled = false;
    const loadDocuments = async () => {
      setUploadedDocumentsLoading(true);
      setUploadedDocumentsError(null);
      try {
        const documents = await listUploadedDocuments({
          search: documentSearch.trim() || undefined,
          document_type: documentTypeFilter || undefined,
          document_category: documentCategoryFilter || undefined,
          related_vendor_id: documentEntityFilter || undefined,
          uploaded_only: true,
        });
        if (!cancelled) {
          setUploadedDocuments(documents);
          setSelectedUploadedDocumentId((current) => current && documents.some((document) => document.document_id === current) ? current : documents[0]?.document_id ?? null);
          setIsDocumentDetailOpen(false);
        }
      } catch (err) {
        if (!cancelled) {
          setUploadedDocuments([]);
          setUploadedDocumentsError(err instanceof Error ? err.message : 'Unable to load uploaded documents.');
        }
      } finally {
        if (!cancelled) {
          setUploadedDocumentsLoading(false);
        }
      }
    };
    void loadDocuments();
    return () => {
      cancelled = true;
    };
  }, [documentSearch, documentTypeFilter, documentCategoryFilter, documentEntityFilter, documentRefreshTick, realtimeTick]);

  const updateField = <K extends keyof DatabaseConnectionForm>(field: K, value: DatabaseConnectionForm[K]) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleTest = async () => {
    setActionLoading(true);
    setTestMessage(null);
    setError(null);
    try {
      const result = await testDatabaseConnection(form);
      setTestMessage(
        cleanConnectionTestMessage(
          result.success
            ? `Connection successful. ${result.schemas.length} schemas and ${result.tables.length} tables detected.`
            : result.message,
          result.success,
        ),
      );
    } catch (err) {
      setTestMessage(
        cleanConnectionTestMessage(err instanceof Error ? err.message : 'Connection test failed.', false),
      );
    } finally {
      setActionLoading(false);
    }
  };

  const handleSave = async () => {
    setActionLoading(true);
    setError(null);
    try {
      const result = await createDatabaseConnection(form);
      setMessage(result.message || 'Connection saved.');
      setSelectedConnectionIdState(result.connection.connection_id);
      setSelectedDatabaseConnectionId(result.connection.connection_id);
      await loadConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save connection.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleActivate = async (connectionId: string) => {
    setActionLoading(true);
    setError(null);
    try {
      const connection = await activateDatabaseConnection(connectionId);
      setSelectedConnectionIdState(connection.connection_id);
      setSelectedDatabaseConnectionId(connection.connection_id);
      setMessage(`${connection.connection_name} is now the active source.`);
      await loadConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to activate connection.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async (connectionId: string) => {
    setActionLoading(true);
    setError(null);
    try {
      await deleteDatabaseConnection(connectionId);
      if (selectedConnectionId === connectionId) {
        setSelectedConnectionIdState(null);
        setSelectedDatabaseConnectionId(null);
      }
      await loadConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to delete connection.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveSelection = async () => {
    if (!selectedConnectionId) return;
    setActionLoading(true);
    setError(null);
    try {
      await updateDatabaseConnectionSelection(selectedConnectionId, {
        selected_schemas: selectedSchemas,
        selected_tables: selectedTables,
      });
      setMessage('Selection saved.');
      await loadConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save selection.');
    } finally {
      setActionLoading(false);
    }
  };

  const toggleSchema = (schemaName: string) => {
    setSelectedSchemas((prev) => (prev.includes(schemaName) ? prev.filter((item) => item !== schemaName) : [...prev, schemaName]));
  };

  const toggleTable = (tableName: string) => {
    setSelectedTables((prev) => (prev.includes(tableName) ? prev.filter((item) => item !== tableName) : [...prev, tableName]));
  };

  const loadTableDetail = async (schemaName: string, tableName: string) => {
    if (!selectedConnectionId) {
      return;
    }
    setTableDetailLoading(true);
    setTableDetailError(null);
    try {
      const detail = await getDatabaseConnectionTableDetail(selectedConnectionId, schemaName, tableName);
      setSelectedTableDetail(detail);
      setIsTablePreviewOpen(true);
    } catch (err) {
      setTableDetailError(err instanceof Error ? err.message : 'Unable to load table details.');
    } finally {
      setTableDetailLoading(false);
    }
  };

  const openDocumentDetail = (documentId: string) => {
    setSelectedUploadedDocumentId(documentId);
    setIsDocumentDetailOpen(true);
  };

  const updateUploadField = <K extends keyof DocumentUploadDraft>(field: K, value: DocumentUploadDraft[K]) => {
    setUploadDraft((prev) => ({ ...prev, [field]: value }));
  };

  const handleDocumentUpload = async () => {
    if (!uploadDraft.file) {
      setUploadError('Please choose a document before uploading.');
      return;
    }
    setUploadLoading(true);
    setUploadError(null);
    setUploadMessage(null);
    setUploadProcessing(null);
    try {
      const payload: DocumentUploadForm = {
        file: uploadDraft.file,
        document_type: uploadDraft.document_type || undefined,
        document_category: uploadDraft.document_category || undefined,
        related_vendor_id: uploadDraft.related_vendor_id || undefined,
        related_employee_id: uploadDraft.related_employee_id || undefined,
        related_transaction_id: uploadDraft.related_transaction_id || undefined,
        related_contract_id: uploadDraft.related_contract_id || undefined,
        related_investigation_id: uploadDraft.related_investigation_id || undefined,
      };
      const result = await uploadDocumentSource(payload);
      setUploadMessage(result.message || 'Document uploaded successfully.');
      setUploadProcessing(result.processing || null);
      setUploadDraft(DEFAULT_UPLOAD_DRAFT);
      setDocumentRefreshTick((tick) => tick + 1);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Unable to upload document.');
    } finally {
      setUploadLoading(false);
    }
  };

  return (
    <div className="stack" style={{ gap: '1.25rem' }}>
      <div className="flex-between" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <p className="eyebrow" style={{ marginBottom: '0.35rem' }}>Data Sources</p>
          <h1 style={{ fontSize: '1.55rem', fontWeight: 800 }}>
            {isAdminView ? 'Admin Source Console' : 'Source Connections'}
          </h1>
          <p className="body-copy" style={{ marginTop: '0.35rem' }}>
            Add a database source, test it, and choose which schema and tables the audit assistant should use.
          </p>
        </div>
        {activeConnection && (
          <div className="card-sm" style={{ minWidth: 260 }}>
            <p className="label">Active Source</p>
            <strong>{activeConnection.connection_name}</strong>
            <p className="small-copy">
              {activeConnection.database_type.toUpperCase()} | {activeConnection.host}:{activeConnection.port}
            </p>
          </div>
        )}
      </div>

      {error && <FeedbackBanner title="Source Error" message={error} variant="error" />}

      {message && <FeedbackBanner title="Status" message={message} variant="success" />}

      <div className="card">
        <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.85rem' }}>
          <div>
            <p className="label" style={{ marginBottom: '0.25rem' }}>Source Journey</p>
            <strong style={{ fontSize: '1rem' }}>Setup your audit data source</strong>
            <p className="small-copy" style={{ marginTop: '0.3rem' }}>
              Test the connection, save it, choose the schema and tables, then upload supporting documents if needed.
            </p>
          </div>
          <span className="source-pill">
            {selectedSchemas.length} schema(s) · {selectedTables.length} table(s)
          </span>
        </div>

        <div className="grid-auto" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
          {sourceJourney.map((step) => (
            <div
              key={step.label}
              className="card-sm"
              style={{
                borderLeft: `3px solid ${step.complete ? 'var(--accent-green)' : 'var(--border)'}`,
                background: step.complete ? 'rgba(16,185,129,0.04)' : 'var(--bg-card)',
              }}
            >
              <p className="label" style={{ marginBottom: '0.3rem' }}>{step.label}</p>
              <strong style={{ display: 'block', marginBottom: '0.35rem' }}>{step.complete ? 'Complete' : 'Pending'}</strong>
              <p className="small-copy">{step.detail}</p>
            </div>
          ))}
        </div>
      </div>
      {isAdminView && (
        <div className="card-sm" style={{ borderLeft: '3px solid var(--accent-blue)' }}>
          <p className="label" style={{ marginBottom: '0.35rem' }}>Admin Access</p>
          <p className="body-copy">
            This console is reserved for privileged source administration. Non-admin users only see their own saved sources.
          </p>
        </div>
      )}

      <div className="grid-2" style={{ gap: '1rem', alignItems: 'start' }}>
        <div className="card">
          <p className="label" style={{ marginBottom: '0.8rem' }}>Add Source</p>
          <div className="stack-sm">
            <input
              className="input"
              placeholder="Connection name"
              value={form.connection_name}
              onChange={(e) => updateField('connection_name', e.target.value)}
            />
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <span className="label" style={{ marginBottom: 0 }}>Source type</span>
              <select className="input" value={form.database_type} onChange={(e) => updateField('database_type', e.target.value)}>
                {DATABASE_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid-2" style={{ gap: '0.75rem' }}>
              <input className="input" placeholder="Host" value={form.host} onChange={(e) => updateField('host', e.target.value)} />
              <input className="input" type="number" placeholder="Port" value={form.port} onChange={(e) => updateField('port', Number(e.target.value))} />
            </div>
            <input className="input" placeholder="Database name" value={form.database_name} onChange={(e) => updateField('database_name', e.target.value)} />
            <div className="grid-2" style={{ gap: '0.75rem' }}>
              <input className="input" placeholder="Username" value={form.username} onChange={(e) => updateField('username', e.target.value)} />
              <input className="input" type="password" placeholder="Password" value={form.password} onChange={(e) => updateField('password', e.target.value)} />
            </div>
            <div className="flex-row" style={{ gap: '0.5rem', flexWrap: 'wrap' }}>
            <button className="btn btn-secondary" type="button" onClick={handleTest} disabled={actionLoading}>
              Test Source
            </button>
              <button className="btn btn-primary" type="button" onClick={handleSave} disabled={actionLoading}>
                Save Source
              </button>
            </div>
            {testMessage && (
              <FeedbackBanner
                title={testMessage.toLowerCase().startsWith('connection successful') ? 'Connection Check Passed' : 'Connection Check Failed'}
                message={testMessage}
                variant={testMessage.toLowerCase().startsWith('connection successful') ? 'success' : 'error'}
              />
            )}
          </div>
        </div>

        <div className="card">
          <p className="label" style={{ marginBottom: '0.8rem' }}>Saved Sources</p>
          {loading ? (
            <p className="body-copy">Loading sources...</p>
          ) : connections.length === 0 ? (
            <p className="body-copy">No data sources saved yet.</p>
          ) : (
            <div className="stack-sm">
              {connections.map((connection) => (
                <div
                  key={connection.connection_id}
                  className="card-sm"
                  style={{ borderLeft: connection.is_default ? '3px solid var(--accent-blue)' : '3px solid transparent' }}
                >
                  <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
                    <div>
                      <strong>{connection.connection_name}</strong>
                      <p className="small-copy">{connection.database_type.toUpperCase()} | {connection.host}:{connection.port} | {connection.database_name}</p>
                      <p className="small-copy">Last tested: {prettyDate(connection.last_tested_at)}</p>
                    </div>
                    <div className="flex-row" style={{ gap: '0.45rem', flexWrap: 'wrap' }}>
                      {connection.is_default ? <span className="source-pill">Active</span> : null}
                      <button className="btn btn-ghost" type="button" onClick={() => handleActivate(connection.connection_id)} disabled={actionLoading}>
                        Use
                      </button>
                      <button className="btn btn-ghost" type="button" onClick={() => handleDelete(connection.connection_id)} disabled={actionLoading}>
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <p className="label" style={{ marginBottom: '0.8rem' }}>Upload Document</p>
        <div className="grid-2" style={{ gap: '0.75rem', alignItems: 'start' }}>
          <div className="stack-sm">
            <input
              className="input"
              type="file"
              accept=".pdf,.docx,.txt,.eml,.md,.csv"
              onChange={(event) => updateUploadField('file', event.target.files?.[0] || null)}
            />
            <div className="grid-2" style={{ gap: '0.75rem' }}>
              <input
                className="input"
                placeholder="Document type"
                value={uploadDraft.document_type}
                onChange={(event) => updateUploadField('document_type', event.target.value)}
              />
              <input
                className="input"
                placeholder="Document category"
                value={uploadDraft.document_category}
                onChange={(event) => updateUploadField('document_category', event.target.value)}
              />
            </div>
            <div className="grid-2" style={{ gap: '0.75rem' }}>
              <input
                className="input"
                placeholder="Vendor ID"
                value={uploadDraft.related_vendor_id}
                onChange={(event) => updateUploadField('related_vendor_id', event.target.value)}
              />
              <input
                className="input"
                placeholder="Employee ID"
                value={uploadDraft.related_employee_id}
                onChange={(event) => updateUploadField('related_employee_id', event.target.value)}
              />
            </div>
            <div className="grid-2" style={{ gap: '0.75rem' }}>
              <input
                className="input"
                placeholder="Transaction ID"
                value={uploadDraft.related_transaction_id}
                onChange={(event) => updateUploadField('related_transaction_id', event.target.value)}
              />
              <input
                className="input"
                placeholder="Contract ID"
                value={uploadDraft.related_contract_id}
                onChange={(event) => updateUploadField('related_contract_id', event.target.value)}
              />
            </div>
            <input
              className="input"
              placeholder="Investigation ID"
              value={uploadDraft.related_investigation_id}
              onChange={(event) => updateUploadField('related_investigation_id', event.target.value)}
            />
            <div className="flex-row" style={{ gap: '0.5rem', flexWrap: 'wrap' }}>
              <button className="btn btn-primary" type="button" onClick={handleDocumentUpload} disabled={uploadLoading}>
                {uploadLoading ? 'Processing...' : 'Upload and Process'}
              </button>
              <span className="small-copy">
                The uploaded document is extracted, classified, and linked to the source console.
              </span>
            </div>
          </div>

          <div className="stack-sm">
            {uploadError && <FeedbackBanner title="Upload Error" message={uploadError} variant="error" />}
            {uploadMessage && <FeedbackBanner title="Upload Status" message={uploadMessage} variant="success" />}
            {uploadProcessing && (
              <div className="card-sm" style={{ borderLeft: '3px solid var(--accent-blue)' }}>
                <p className="label" style={{ marginBottom: '0.35rem' }}>Processing Summary</p>
                <p className="body-copy" style={{ marginBottom: '0.55rem' }}>
                  {uploadProcessing.processing_summary || 'The uploaded document was processed successfully.'}
                </p>
                <div className="grid-2" style={{ gap: '0.6rem' }}>
                  <InfoTile label="Detected Type" value={(uploadProcessing.file_type || 'document').toUpperCase()} />
                  <InfoTile label="Content Length" value={`${(uploadProcessing.content_length || 0).toLocaleString()} characters`} />
                  <InfoTile label="Signals" value={(uploadProcessing.signals || []).length > 0 ? (uploadProcessing.signals || []).join(', ') : 'None detected'} />
                  <InfoTile label="Status" value={uploadProcessing.supported ? 'Processed' : 'Stored only'} />
                </div>
                {uploadProcessing.content_snippet && (
                  <div style={{ marginTop: '0.65rem' }}>
                    <p className="label" style={{ marginBottom: '0.35rem' }}>Extracted Snippet</p>
                    <p className="small-copy" style={{ whiteSpace: 'pre-wrap' }}>{uploadProcessing.content_snippet}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ gap: '1rem', alignItems: 'start' }}>
        <div className="card">
          <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.8rem' }}>
            <p className="label" style={{ marginBottom: 0 }}>Uploaded Documents</p>
            <span className="badge badge-completed">{uploadedDocuments.length} item{uploadedDocuments.length === 1 ? '' : 's'}</span>
          </div>
          <div className="grid-2" style={{ gap: '0.6rem', marginBottom: '0.8rem' }}>
            <input
              className="input"
              placeholder="Search documents"
              value={documentSearch}
              onChange={(event) => setDocumentSearch(event.target.value)}
            />
            <input
              className="input"
              placeholder="Filter by linked entity ID"
              value={documentEntityFilter}
              onChange={(event) => setDocumentEntityFilter(event.target.value)}
            />
            <select className="input" value={documentTypeFilter} onChange={(event) => setDocumentTypeFilter(event.target.value)}>
              <option value="">All document types</option>
              {DOCUMENT_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            <select className="input" value={documentCategoryFilter} onChange={(event) => setDocumentCategoryFilter(event.target.value)}>
              <option value="">All categories</option>
              {DOCUMENT_CATEGORY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>
          {uploadedDocumentsError && <FeedbackBanner title="Document Feed Error" message={uploadedDocumentsError} variant="error" />}
          {uploadedDocumentsLoading ? (
            <p className="small-copy">Loading uploaded documents...</p>
          ) : uploadedDocuments.length === 0 ? (
            <p className="small-copy">No uploaded documents found.</p>
          ) : (
            <div className="stack-sm">
              {uploadedDocuments.map((document) => (
                <button
                  key={document.document_id}
                  type="button"
                  className={`card-sm${selectedUploadedDocumentId === document.document_id ? ' active' : ''}`}
                  onClick={() => openDocumentDetail(document.document_id)}
                  style={{ textAlign: 'left' }}
                >
                  <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
                    <strong>{document.file_name}</strong>
                    <span className="source-pill">{document.document_category}</span>
                  </div>
                  <p className="small-copy" style={{ marginTop: '0.35rem' }}>
                    {document.document_type.toUpperCase()} • {document.document_id}
                  </p>
                  <p className="small-copy">
                    Linked to {document.related_vendor_id || document.related_transaction_id || document.related_contract_id || document.related_employee_id || document.related_investigation_id || 'no entity'}
                  </p>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <p className="label" style={{ marginBottom: '0.8rem' }}>Document Details</p>
          {selectedUploadedDocumentId ? (
            (() => {
              const document = uploadedDocuments.find((item) => item.document_id === selectedUploadedDocumentId) || null;
              if (!document) {
                return <p className="small-copy">Select a document to inspect its details.</p>;
              }
              return (
                <div className="stack-sm">
                  <div className="card-sm">
                    <strong>{document.file_name}</strong>
                    <p className="small-copy" style={{ marginTop: '0.35rem' }}>{document.document_category} • {document.document_type.toUpperCase()}</p>
                  </div>
                  <div className="grid-2" style={{ gap: '0.6rem' }}>
                    <InfoTile label="Document ID" value={document.document_id} />
                    <InfoTile label="Source URI" value={document.source_uri} />
                    <InfoTile label="Created" value={new Date(document.creation_date).toLocaleDateString()} />
                    <InfoTile label="Source Metadata" value={document.source_metadata_file} />
                  </div>
                  <div className="card-sm">
                    <p className="label">Linked Entities</p>
                    <div className="stack-sm" style={{ marginTop: '0.5rem' }}>
                      <InfoTile label="Vendor" value={document.related_vendor_id || '—'} />
                      <InfoTile label="Employee" value={document.related_employee_id || '—'} />
                      <InfoTile label="Transaction" value={document.related_transaction_id || '—'} />
                      <InfoTile label="Contract" value={document.related_contract_id || '—'} />
                      <InfoTile label="Investigation" value={document.related_investigation_id || '—'} />
                    </div>
                  </div>
                  <div className="card-sm">
                    <p className="label">Storage Path</p>
                    <p className="small-copy" style={{ marginTop: '0.35rem', wordBreak: 'break-all' }}>{document.file_path}</p>
                  </div>
                </div>
              );
            })()
          ) : (
            <p className="small-copy">Select an uploaded document to inspect its metadata and linked entities.</p>
          )}
        </div>
      </div>


      {isDocumentDetailOpen && selectedUploadedDocumentId && (() => {
        const document = uploadedDocuments.find((item) => item.document_id === selectedUploadedDocumentId) || null;
        if (!document) {
          return null;
        }

        return (
          <div
            role="presentation"
            onClick={() => setIsDocumentDetailOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 65,
              background: 'rgba(8, 15, 35, 0.66)',
              backdropFilter: 'blur(4px)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '1rem',
            }}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Document details"
              onClick={(event) => event.stopPropagation()}
              className="card"
              style={{
                width: 'min(980px, 100%)',
                maxHeight: '88vh',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.9rem',
              boxShadow: '0 24px 60px rgba(15,23,42,0.28)',
              }}
            >
              <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
                <div>
                  <p className="label" style={{ marginBottom: '0.25rem' }}>Document Details</p>
                  <strong style={{ fontSize: '1.05rem' }}>{document.file_name}</strong>
                  <p className="small-copy" style={{ marginTop: '0.35rem' }}>
                    {document.document_category} ? {document.document_type.toUpperCase()}
                  </p>
                </div>
                <div className="flex-row" style={{ gap: '0.5rem', flexWrap: 'wrap' }}>
                  <span className="source-pill">Registered</span>
                  <button type="button" className="btn btn-ghost" onClick={() => setIsDocumentDetailOpen(false)}>
                    Close
                  </button>
                </div>
              </div>

              <div style={{ overflowY: 'auto', paddingRight: '0.25rem' }}>
                <div className="stack-sm">
                  <div className="grid-2" style={{ gap: '0.6rem' }}>
                    <InfoTile label="Document ID" value={document.document_id} />
                    <InfoTile label="Document Type" value={document.document_type.toUpperCase()} />
                    <InfoTile label="Category" value={document.document_category} />
                    <InfoTile label="Created" value={prettyDate(document.created_at || document.creation_date)} />
                  </div>

                  <div className="card-sm">
                    <p className="label" style={{ marginBottom: '0.5rem' }}>Processing Status</p>
                    <div className="grid-2" style={{ gap: '0.6rem' }}>
                      <InfoTile label="Status" value="Uploaded and registered" />
                      <InfoTile label="Pipeline" value="Ready for document processing" />
                      <InfoTile label="Source Metadata File" value={document.source_metadata_file} />
                      <InfoTile label="Source URI" value={document.source_uri} />
                    </div>
                  </div>

                  <div className="card-sm">
                    <p className="label">Linked Entities</p>
                    <div className="stack-sm" style={{ marginTop: '0.5rem' }}>
                      <InfoTile label="Vendor" value={document.related_vendor_id || '?'} />
                      <InfoTile label="Employee" value={document.related_employee_id || '?'} />
                      <InfoTile label="Transaction" value={document.related_transaction_id || '?'} />
                      <InfoTile label="Contract" value={document.related_contract_id || '?'} />
                      <InfoTile label="Investigation" value={document.related_investigation_id || '?'} />
                    </div>
                  </div>

                  <div className="card-sm">
                    <p className="label" style={{ marginBottom: '0.45rem' }}>Storage Path</p>
                    <p className="small-copy" style={{ wordBreak: 'break-all' }}>{document.file_path}</p>
                  </div>

                  <div className="card-sm">
                    <p className="label" style={{ marginBottom: '0.45rem' }}>Processing Notes</p>
                    <p className="small-copy">
                      The file has been stored in the document repository and linked to the workspace. The next ingestion step can extract text, sections, and citations for retrieval.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {selectedConnection && (
        <div className="card">
          <div className="flex-between" style={{ marginBottom: '0.8rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <p className="label" style={{ marginBottom: '0.25rem' }}>Selected Source</p>
              <strong>{selectedConnection.connection_name}</strong>
              <p className="small-copy">
                {selectedConnection.database_type.toUpperCase()} | {selectedConnection.host}:{selectedConnection.port} | {selectedConnection.database_name}
              </p>
            </div>
            <button className="btn btn-primary" type="button" onClick={handleSaveSelection} disabled={actionLoading}>
              Save Schema and Table Selection
            </button>
          </div>

          <div className="grid-2" style={{ gap: '1rem', alignItems: 'start' }}>
            <div className="card-sm">
              <p className="label" style={{ marginBottom: '0.6rem' }}>Schemas</p>
              <div className="stack-sm">
                {schemas.length > 0 ? (
                  schemas.map((schema) => (
                    <label
                      key={schema.schema_name}
                      className="flex-between"
                      style={{ gap: '0.75rem', padding: '0.45rem 0', borderBottom: '1px solid var(--border)' }}
                    >
                      <span style={{ display: 'flex', flexDirection: 'column' }}>
                        <strong style={{ fontSize: '0.88rem' }}>{schema.schema_name}</strong>
                        <span className="small-copy">{schema.table_count} table(s)</span>
                      </span>
                      <input
                        type="checkbox"
                        checked={selectedSchemas.includes(schema.schema_name)}
                        onChange={() => toggleSchema(schema.schema_name)}
                      />
                    </label>
                  ))
                ) : (
                  <p className="body-copy">No schema metadata available.</p>
                )}
              </div>
            </div>

            <div className="card-sm">
              <p className="label" style={{ marginBottom: '0.6rem' }}>Tables</p>
              <div className="stack-sm">
                {tables.length > 0 ? (
                  tables.map((table) => (
                    <div
                      key={`${table.schema_name}.${table.table_name}`}
                      className={`card-sm${selectedTableDetail?.table_name === table.table_name && selectedTableDetail?.schema_name === table.schema_name ? ' active' : ''}`}
                      style={{ padding: '0.75rem', marginBottom: '0.6rem' }}
                    >
                      <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          onClick={() => void loadTableDetail(table.schema_name, table.table_name)}
                          className="btn btn-ghost"
                          style={{ padding: '0', textAlign: 'left', minWidth: 0 }}
                        >
                          <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                            <strong style={{ fontSize: '0.88rem' }}>{table.table_name}</strong>
                            <span className="small-copy">{table.schema_name}</span>
                          </span>
                        </button>
                        <input
                          type="checkbox"
                          checked={selectedTables.includes(table.table_name)}
                          onChange={() => toggleTable(table.table_name)}
                        />
                      </div>
                      <div className="flex-between" style={{ gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                        <span className="source-pill">{table.column_count} column{table.column_count === 1 ? '' : 's'}</span>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => void loadTableDetail(table.schema_name, table.table_name)}
                        >
                          Open Preview
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="body-copy">No table metadata available.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {isTablePreviewOpen && selectedTableDetail && (
        <div
          role="presentation"
          onClick={() => setIsTablePreviewOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 999,
            background: 'rgba(8, 15, 35, 0.66)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Table preview"
            onClick={(event) => event.stopPropagation()}
            className="card"
            style={{
              width: 'min(1120px, 100%)',
              maxHeight: '88vh',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.9rem',
              boxShadow: '0 24px 60px rgba(15,23,42,0.28)',
            }}
          >
            <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
              <div>
                <p className="label" style={{ marginBottom: '0.25rem' }}>Table Preview</p>
                <strong style={{ fontSize: '1.05rem' }}>{selectedTableDetail.schema_name}.{selectedTableDetail.table_name}</strong>
                <p className="small-copy" style={{ marginTop: '0.35rem' }}>{selectedTableDetail.summary}</p>
              </div>
              <div className="flex-row" style={{ gap: '0.5rem', flexWrap: 'wrap' }}>
                {tableDetailLoading && <span className="source-pill">Loading preview...</span>}
                <button type="button" className="btn btn-ghost" onClick={() => setIsTablePreviewOpen(false)}>
                  Close
                </button>
              </div>
            </div>

            {tableDetailError && <FeedbackBanner title="Table Preview Error" message={tableDetailError} variant="error" />}

            <div style={{ overflowY: 'auto', paddingRight: '0.25rem' }}>
              <div className="stack-sm">
                <div className="grid-auto" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
                  <div className="card-sm">
                    <p className="label">Schema</p>
                    <strong>{selectedTableDetail.schema_name}</strong>
                  </div>
                  <div className="card-sm">
                    <p className="label">Table</p>
                    <strong>{selectedTableDetail.table_name}</strong>
                  </div>
                  <div className="card-sm">
                    <p className="label">Preview Mode</p>
                    <strong>Summary + Sample Data</strong>
                  </div>
                </div>
                <div className="grid-auto" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
                  <div className="card-sm">
                    <p className="label">Rows</p>
                    <strong>{selectedTableDetail.row_count.toLocaleString()}</strong>
                  </div>
                  <div className="card-sm">
                    <p className="label">Columns</p>
                    <strong>{selectedTableDetail.column_count}</strong>
                  </div>
                  <div className="card-sm">
                    <p className="label">Primary Key</p>
                    <p className="small-copy">
                      {selectedTableDetail.primary_key_columns.length > 0
                        ? selectedTableDetail.primary_key_columns.join(', ')
                        : 'Not detected'}
                    </p>
                  </div>
                </div>

                <div className="card-sm">
                  <p className="label" style={{ marginBottom: '0.45rem' }}>Columns</p>
                  <div className="stack-sm">
                    {selectedTableDetail.column_details.map((column) => (
                      <div key={column.name} className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
                        <strong style={{ fontSize: '0.88rem' }}>{column.name}</strong>
                        <span className="small-copy">
                          {column.data_type || 'unknown'}
                          {column.nullable === false ? ' ? required' : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="card-sm">
                  <p className="label" style={{ marginBottom: '0.45rem' }}>Sample Rows</p>
                  {selectedTableDetail.sample_rows.length > 0 ? (
                    <div style={{ overflowX: 'auto' }}>
                      <table className="table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr>
                            {Object.keys(selectedTableDetail.sample_rows[0] || {}).map((key) => (
                              <th key={key} style={{ textAlign: 'left', padding: '0.45rem 0.5rem' }}>{key}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {selectedTableDetail.sample_rows.map((row, index) => (
                            <tr key={index}>
                              {Object.keys(selectedTableDetail.sample_rows[0] || {}).map((key) => (
                                <td key={key} style={{ padding: '0.45rem 0.5rem', borderTop: '1px solid var(--border)' }}>
                                  {String(row[key] ?? '?')}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="small-copy">No sample rows available.</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

