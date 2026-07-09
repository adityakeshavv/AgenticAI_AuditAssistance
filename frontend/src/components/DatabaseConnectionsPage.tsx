import { useEffect, useMemo, useState } from 'react';
import {
  activateDatabaseConnection,
  createDatabaseConnection,
  deleteDatabaseConnection,
  getDatabaseConnection,
  getDatabaseConnectionSchemas,
  getDatabaseConnectionTables,
  getSelectedDatabaseConnectionId,
  listDatabaseConnections,
  setSelectedDatabaseConnectionId,
  updateDatabaseConnectionSelection,
  testDatabaseConnection,
} from '../services/databaseConnectionsApi';
import type {
  DatabaseConnectionForm,
  DatabaseConnectionRecord,
  DatabaseConnectionSchemaInfo,
  DatabaseConnectionTableInfo,
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

function prettyDate(value?: string | null) {
  if (!value) return 'n/a';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

type DatabaseConnectionsPageProps = {
  isAdminView?: boolean;
};

export function DatabaseConnectionsPage({ isAdminView = false }: DatabaseConnectionsPageProps) {
  const [connections, setConnections] = useState<DatabaseConnectionRecord[]>([]);
  const [selectedConnectionId, setSelectedConnectionIdState] = useState<string | null>(getSelectedDatabaseConnectionId());
  const [selectedConnection, setSelectedConnection] = useState<DatabaseConnectionRecord | null>(null);
  const [schemas, setSchemas] = useState<DatabaseConnectionSchemaInfo[]>([]);
  const [tables, setTables] = useState<DatabaseConnectionTableInfo[]>([]);
  const [selectedSchemas, setSelectedSchemas] = useState<string[]>([]);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
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
      setSchemas(await getDatabaseConnectionSchemas(connectionId));
      setTables(await getDatabaseConnectionTables(connectionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load connection details.');
    }
  };

  useEffect(() => {
    void loadConnections();
  }, []);

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
  }, [selectedConnectionId]);

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
        result.success
          ? `Connection successful. ${result.schemas.length} schemas and ${result.tables.length} tables detected.`
          : result.message,
      );
    } catch (err) {
      setTestMessage(err instanceof Error ? err.message : 'Connection test failed.');
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
      setSelectedConnectionId(result.connection.connection_id);
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
      setSelectedConnectionId(connection.connection_id);
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

      {error && (
        <div className="card-sm" style={{ borderLeft: '3px solid var(--accent-red)' }}>
          <p className="label" style={{ color: 'var(--accent-red)' }}>Source Error</p>
          <p className="body-copy">{error}</p>
        </div>
      )}

      {message && (
        <div className="card-sm" style={{ borderLeft: '3px solid var(--accent-green)' }}>
          <p className="label" style={{ color: 'var(--accent-green)' }}>Status</p>
          <p className="body-copy">{message}</p>
        </div>
      )}

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
            {testMessage && <p className="small-copy">{testMessage}</p>}
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
                    <label
                      key={`${table.schema_name}.${table.table_name}`}
                      className="flex-between"
                      style={{ gap: '0.75rem', padding: '0.45rem 0', borderBottom: '1px solid var(--border)' }}
                    >
                      <span style={{ display: 'flex', flexDirection: 'column' }}>
                        <strong style={{ fontSize: '0.88rem' }}>{table.table_name}</strong>
                        <span className="small-copy">{table.schema_name}</span>
                      </span>
                      <input
                        type="checkbox"
                        checked={selectedTables.includes(table.table_name)}
                        onChange={() => toggleTable(table.table_name)}
                      />
                    </label>
                  ))
                ) : (
                  <p className="body-copy">No table metadata available.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
