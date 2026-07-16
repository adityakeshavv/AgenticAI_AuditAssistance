import { useEffect, useMemo, useState } from 'react';
import { listDatabaseConnections, getSelectedDatabaseConnectionId, setSelectedDatabaseConnectionId } from '../services/databaseConnectionsApi';
import {
  activateWorkspace,
  createWorkspace,
  deleteWorkspace,
  getSelectedWorkspaceConnectionId,
  getSelectedWorkspaceId,
  listWorkspaces,
  setSelectedWorkspaceConnectionId,
  setSelectedWorkspaceId,
  updateWorkspaceSelection,
} from '../services/workspacesApi';
import type { DatabaseConnectionRecord } from '../types/databaseConnections';
import type { WorkspaceForm, WorkspaceRecord } from '../types/workspace';
import { FeedbackBanner } from './FeedbackBanner';

const DEFAULT_FORM: WorkspaceForm = {
  workspace_name: '',
  description: '',
  selected_connection_ids: [],
  active_connection_id: '',
};

function prettyDate(value?: string | null) {
  if (!value) return 'n/a';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export function WorkspaceManagementPage() {
  const [workspaces, setWorkspaces] = useState<WorkspaceRecord[]>([]);
  const [connections, setConnections] = useState<DatabaseConnectionRecord[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceIdState] = useState<string | null>(getSelectedWorkspaceId());
  const [selectedWorkspace, setSelectedWorkspace] = useState<WorkspaceRecord | null>(null);
  const [selectedConnectionIds, setSelectedConnectionIds] = useState<string[]>([]);
  const [activeConnectionId, setActiveConnectionId] = useState<string>(getSelectedWorkspaceConnectionId() || getSelectedDatabaseConnectionId() || '');
  const [form, setForm] = useState<WorkspaceForm>(DEFAULT_FORM);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeWorkspace = useMemo(
    () => workspaces.find((item) => item.workspace_id === selectedWorkspaceId) || null,
    [selectedWorkspaceId, workspaces],
  );

  const connectionById = useMemo(() => new Map(connections.map((item) => [item.connection_id, item])), [connections]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [workspaceItems, connectionItems] = await Promise.all([listWorkspaces(), listDatabaseConnections()]);
      setWorkspaces(workspaceItems);
      setConnections(connectionItems);
      if (!selectedWorkspaceId && workspaceItems.length > 0) {
        const defaultWorkspace = workspaceItems.find((item) => item.is_default) || workspaceItems[0];
        if (defaultWorkspace) {
          setSelectedWorkspaceIdState(defaultWorkspace.workspace_id);
          setSelectedWorkspaceId(defaultWorkspace.workspace_id);
          setSelectedDatabaseConnectionId(defaultWorkspace.active_connection_id || null);
          setSelectedWorkspaceConnectionId(defaultWorkspace.active_connection_id || null);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load workspaces.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  useEffect(() => {
    if (!selectedWorkspaceId) {
      setSelectedWorkspace(null);
      setSelectedConnectionIds([]);
      return;
    }
    const workspace = workspaces.find((item) => item.workspace_id === selectedWorkspaceId) || null;
    setSelectedWorkspace(workspace);
    if (workspace) {
      setSelectedConnectionIds(workspace.selected_connection_ids || []);
      const activeConnection = workspace.active_connection_id || workspace.selected_connection_ids?.[0] || '';
      setActiveConnectionId(activeConnection);
      setSelectedWorkspaceConnectionId(activeConnection || null);
      setSelectedDatabaseConnectionId(activeConnection || null);
    }
  }, [selectedWorkspaceId, workspaces]);

  const updateField = <K extends keyof WorkspaceForm>(field: K, value: WorkspaceForm[K]) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const saveWorkspace = async () => {
    setActionLoading(true);
    setError(null);
    try {
      const result = await createWorkspace({
        ...form,
        selected_connection_ids: selectedConnectionIds,
        active_connection_id: activeConnectionId,
      });
      setMessage(result.message || 'Workspace saved.');
      setSelectedWorkspaceIdState(result.workspace.workspace_id);
      setSelectedWorkspaceId(result.workspace.workspace_id);
      setSelectedWorkspaceConnectionId(result.workspace.active_connection_id || null);
      setSelectedDatabaseConnectionId(result.workspace.active_connection_id || null);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save workspace.');
    } finally {
      setActionLoading(false);
    }
  };

  const saveSelection = async () => {
    if (!selectedWorkspaceId) return;
    setActionLoading(true);
    setError(null);
    try {
      const result = await updateWorkspaceSelection(selectedWorkspaceId, {
        selected_connection_ids: selectedConnectionIds,
        active_connection_id: activeConnectionId || null,
      });
      setMessage('Workspace selection saved.');
      setSelectedWorkspaceId(result.workspace_id);
      setSelectedWorkspaceConnectionId(result.active_connection_id || null);
      setSelectedDatabaseConnectionId(result.active_connection_id || null);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save workspace selection.');
    } finally {
      setActionLoading(false);
    }
  };

  const activateSelectedWorkspace = async () => {
    if (!selectedWorkspaceId) return;
    setActionLoading(true);
    setError(null);
    try {
      const workspace = await activateWorkspace(selectedWorkspaceId);
      setSelectedWorkspaceIdState(workspace.workspace_id);
      setSelectedWorkspaceId(workspace.workspace_id);
      setSelectedWorkspaceConnectionId(workspace.active_connection_id || null);
      setSelectedDatabaseConnectionId(workspace.active_connection_id || null);
      setMessage(`${workspace.workspace_name} is now active.`);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to activate workspace.');
    } finally {
      setActionLoading(false);
    }
  };

  const removeWorkspace = async (workspaceId: string) => {
    setActionLoading(true);
    setError(null);
    try {
      await deleteWorkspace(workspaceId);
      if (selectedWorkspaceId === workspaceId) {
        setSelectedWorkspaceIdState(null);
        setSelectedWorkspaceId(null);
        setSelectedWorkspaceConnectionId(null);
        setSelectedDatabaseConnectionId(null);
      }
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to delete workspace.');
    } finally {
      setActionLoading(false);
    }
  };

  const toggleConnection = (connectionId: string) => {
    setSelectedConnectionIds((prev) => {
      const next = prev.includes(connectionId) ? prev.filter((id) => id !== connectionId) : [...prev, connectionId];
      if (!next.includes(activeConnectionId) && next.length > 0) {
        setActiveConnectionId(next[0]);
      }
      if (next.length === 0) {
        setActiveConnectionId('');
      }
      return next;
    });
  };

  return (
    <div className="stack" style={{ gap: '1.25rem' }}>
      <div className="flex-between" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <p className="eyebrow" style={{ marginBottom: '0.35rem' }}>Engagements</p>
          <h1 style={{ fontSize: '1.55rem', fontWeight: 800 }}>Workspace Management</h1>
          <p className="body-copy" style={{ marginTop: '0.35rem' }}>
            Group sources into audit workspaces and choose the active source for each investigation.
          </p>
        </div>
        {activeWorkspace && (
          <div className="card-sm" style={{ minWidth: 280 }}>
            <p className="label">Active Workspace</p>
            <strong>{activeWorkspace.workspace_name}</strong>
            <p className="small-copy">
              {activeWorkspace.selected_connection_ids.length} source(s) selected
            </p>
          </div>
        )}
      </div>

      {error && <FeedbackBanner title="Workspace Error" message={error} variant="error" />}

      {message && <FeedbackBanner title="Status" message={message} variant="success" />}

      <div className="grid-2" style={{ gap: '1rem', alignItems: 'start' }}>
        <div className="card">
          <p className="label" style={{ marginBottom: '0.8rem' }}>Create Workspace</p>
          <div className="stack-sm">
            <input className="input" placeholder="Workspace name" value={form.workspace_name} onChange={(e) => updateField('workspace_name', e.target.value)} />
            <textarea className="input" placeholder="Description" value={form.description} onChange={(e) => updateField('description', e.target.value)} />
            <div className="flex-row" style={{ gap: '0.5rem', flexWrap: 'wrap' }}>
              <button className="btn btn-primary" type="button" onClick={saveWorkspace} disabled={actionLoading || !form.workspace_name.trim()}>
                Save Workspace
              </button>
              <button className="btn btn-secondary" type="button" onClick={activateSelectedWorkspace} disabled={actionLoading || !selectedWorkspaceId}>
                Activate Workspace
              </button>
            </div>
          </div>
        </div>

        <div className="card">
          <p className="label" style={{ marginBottom: '0.8rem' }}>Workspaces</p>
          {loading ? (
            <p className="body-copy">Loading workspaces...</p>
          ) : workspaces.length === 0 ? (
            <p className="body-copy">No workspaces saved yet.</p>
          ) : (
            <div className="stack-sm">
              {workspaces.map((workspace) => (
                <div key={workspace.workspace_id} className="card-sm" style={{ borderLeft: workspace.is_default ? '3px solid var(--accent-blue)' : '3px solid transparent' }}>
                  <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={() => setSelectedWorkspaceIdState(workspace.workspace_id)}
                      style={{ textAlign: 'left', justifyContent: 'flex-start' }}
                    >
                      <strong>{workspace.workspace_name}</strong>
                      <p className="small-copy">{workspace.selected_connection_ids.length} selected source(s)</p>
                    </button>
                    <div className="flex-row" style={{ gap: '0.45rem', flexWrap: 'wrap' }}>
                      {workspace.is_default ? <span className="source-pill">Active</span> : null}
                      <button className="btn btn-ghost" type="button" onClick={() => setSelectedWorkspaceIdState(workspace.workspace_id)} disabled={actionLoading}>
                        Open
                      </button>
                      <button className="btn btn-ghost" type="button" onClick={() => removeWorkspace(workspace.workspace_id)} disabled={actionLoading}>
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

      {selectedWorkspace && (
        <div className="card">
          <div className="flex-between" style={{ marginBottom: '0.8rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <p className="label" style={{ marginBottom: '0.25rem' }}>Selected Workspace</p>
              <strong>{selectedWorkspace.workspace_name}</strong>
              <p className="small-copy">{selectedWorkspace.description || 'No description provided.'}</p>
            </div>
            <button className="btn btn-primary" type="button" onClick={saveSelection} disabled={actionLoading}>
              Save Source Selection
            </button>
          </div>

          <div className="grid-2" style={{ gap: '1rem', alignItems: 'start' }}>
            <div className="card-sm">
              <p className="label" style={{ marginBottom: '0.6rem' }}>Available Sources</p>
              <div className="stack-sm">
                {connections.length > 0 ? (
                  connections.map((connection) => (
                    <label
                      key={connection.connection_id}
                      className="flex-between"
                      style={{ gap: '0.75rem', padding: '0.45rem 0', borderBottom: '1px solid var(--border)' }}
                    >
                      <span style={{ display: 'flex', flexDirection: 'column' }}>
                        <strong style={{ fontSize: '0.88rem' }}>{connection.connection_name}</strong>
                        <span className="small-copy">
                          {connection.database_type.toUpperCase()} | {connection.host}:{connection.port} | {connection.database_name}
                        </span>
                      </span>
                      <input
                        type="checkbox"
                        checked={selectedConnectionIds.includes(connection.connection_id)}
                        onChange={() => toggleConnection(connection.connection_id)}
                      />
                    </label>
                  ))
                ) : (
                  <p className="body-copy">No data sources saved yet.</p>
                )}
              </div>
            </div>

            <div className="card-sm">
              <p className="label" style={{ marginBottom: '0.6rem' }}>Active Source</p>
              <div className="stack-sm">
                {selectedConnectionIds.length > 0 ? (
                  selectedConnectionIds.map((connectionId) => {
                    const connection = connectionById.get(connectionId);
                    if (!connection) return null;
                    return (
                      <label
                        key={connectionId}
                        className="flex-between"
                        style={{ gap: '0.75rem', padding: '0.45rem 0', borderBottom: '1px solid var(--border)' }}
                      >
                        <span style={{ display: 'flex', flexDirection: 'column' }}>
                          <strong style={{ fontSize: '0.88rem' }}>{connection.connection_name}</strong>
                          <span className="small-copy">{connection.database_name}</span>
                        </span>
                        <input
                          type="radio"
                          name="activeConnection"
                          checked={activeConnectionId === connectionId}
                          onChange={() => setActiveConnectionId(connectionId)}
                        />
                      </label>
                    );
                  })
                ) : (
                  <p className="body-copy">Select one or more sources to choose the active source.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
