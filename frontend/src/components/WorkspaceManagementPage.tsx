import { useEffect, useMemo, useState } from 'react';
import { listDatabaseConnections, getSelectedDatabaseConnectionId, setSelectedDatabaseConnectionId } from '../services/databaseConnectionsApi';
import {
  createWorkspaceCollaborationItem,
  deleteWorkspaceCollaborationItem,
  listWorkspaceCollaborationItems,
  updateWorkspaceCollaborationItem,
} from '../services/workspaceCollaborationApi';
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
import type {
  WorkspaceCollaborationItem,
  WorkspaceCollaborationItemType,
  WorkspaceCollaborationSummary,
} from '../types/workspaceCollaboration';
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

const DEFAULT_COLLAB_FORM = {
  item_type: 'comment' as WorkspaceCollaborationItemType,
  title: '',
  body: '',
  status: 'open',
  priority: 'medium',
  mentions_text: '',
  assignee_user_id: '',
  due_date: '',
};

const EMPTY_COLLAB_SUMMARY: WorkspaceCollaborationSummary = {
  total_items: 0,
  open_items: 0,
  completed_items: 0,
  comment_count: 0,
  task_count: 0,
  review_count: 0,
  mention_count: 0,
};

function formatCollaborationLabel(value: string | null | undefined, fallback = 'n/a') {
  if (!value) return fallback;
  return value
    .split(/[_\-\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function summarizeCollaborationItem(item: WorkspaceCollaborationItem): string {
  const body = (item.body || '').replace(/\s+/g, ' ').trim();
  if (!body) return 'No details added yet.';
  if (body.length <= 120) return body;
  return `${body.slice(0, 119).trimEnd()}...`;
}

function parseMentions(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((entry) => entry.trim().replace(/^@/, ''))
    .filter(Boolean);
}

interface WorkspaceManagementPageProps {
  realtimeTick?: number;
}

export function WorkspaceManagementPage({ realtimeTick = 0 }: WorkspaceManagementPageProps) {
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
  const [collaborationItems, setCollaborationItems] = useState<WorkspaceCollaborationItem[]>([]);
  const [collaborationSummary, setCollaborationSummary] = useState<WorkspaceCollaborationSummary>(EMPTY_COLLAB_SUMMARY);
  const [collaborationLoading, setCollaborationLoading] = useState(false);
  const [collaborationActionLoading, setCollaborationActionLoading] = useState(false);
  const [collaborationError, setCollaborationError] = useState<string | null>(null);
  const [collaborationMessage, setCollaborationMessage] = useState<string | null>(null);
  const [collaborationFilter, setCollaborationFilter] = useState<'all' | WorkspaceCollaborationItemType>('all');
  const [collaborationForm, setCollaborationForm] = useState(DEFAULT_COLLAB_FORM);

  const activeWorkspace = useMemo(
    () => workspaces.find((item) => item.workspace_id === selectedWorkspaceId) || null,
    [selectedWorkspaceId, workspaces],
  );

  const connectionById = useMemo(() => new Map(connections.map((item) => [item.connection_id, item])), [connections]);
  const setupSteps = [
    {
      label: 'Workspace',
      detail: selectedWorkspaceId ? 'Workspace selected' : 'Create or choose one',
      complete: Boolean(selectedWorkspaceId),
    },
    {
      label: 'Sources',
      detail: selectedWorkspace?.selected_connection_ids?.length
        ? `${selectedWorkspace.selected_connection_ids.length} source(s) linked`
        : 'Select data sources',
      complete: Boolean(selectedWorkspace?.selected_connection_ids?.length),
    },
    {
      label: 'Active Source',
      detail: selectedWorkspace?.active_connection_id
        ? 'Active source set'
        : 'Choose the working source',
      complete: Boolean(selectedWorkspace?.active_connection_id),
    },
    {
      label: 'Audit Ready',
      detail: selectedWorkspace?.is_active ? 'Ready for investigations' : 'Activate the workspace',
      complete: Boolean(selectedWorkspace?.is_active && selectedWorkspace?.active_connection_id),
    },
  ];

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
  }, [realtimeTick]);

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

  useEffect(() => {
    const loadCollaboration = async () => {
      if (!selectedWorkspaceId) {
        setCollaborationItems([]);
        setCollaborationSummary(EMPTY_COLLAB_SUMMARY);
        return;
      }
      setCollaborationLoading(true);
      setCollaborationError(null);
      try {
        const result = await listWorkspaceCollaborationItems(selectedWorkspaceId, collaborationFilter === 'all' ? null : collaborationFilter);
        setCollaborationItems(result.items || []);
        setCollaborationSummary(result.summary || EMPTY_COLLAB_SUMMARY);
      } catch (err) {
        setCollaborationError(err instanceof Error ? err.message : 'Unable to load collaboration items.');
      } finally {
        setCollaborationLoading(false);
      }
    };

    void loadCollaboration();
  }, [collaborationFilter, realtimeTick, selectedWorkspaceId]);

  const updateField = <K extends keyof WorkspaceForm>(field: K, value: WorkspaceForm[K]) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const updateCollaborationField = <K extends keyof typeof DEFAULT_COLLAB_FORM>(field: K, value: (typeof DEFAULT_COLLAB_FORM)[K]) => {
    setCollaborationForm((prev) => ({ ...prev, [field]: value }));
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

  const saveCollaborationItem = async () => {
    if (!selectedWorkspaceId) return;
    if (!collaborationForm.body.trim() && !collaborationForm.title.trim()) {
      setCollaborationError('Add a note, task, or review summary before saving.');
      return;
    }

    setCollaborationActionLoading(true);
    setCollaborationError(null);
    setCollaborationMessage(null);
    try {
      await createWorkspaceCollaborationItem(selectedWorkspaceId, {
        item_type: collaborationForm.item_type,
        title: collaborationForm.title.trim() || null,
        body: collaborationForm.body.trim() || null,
        status: collaborationForm.status.trim() || null,
        priority: collaborationForm.priority.trim() || null,
        mentions: parseMentions(collaborationForm.mentions_text),
        assignee_user_id: collaborationForm.assignee_user_id.trim() || null,
        due_date: collaborationForm.due_date || null,
      });
      setCollaborationMessage('Workspace collaboration item saved.');
      setCollaborationForm(DEFAULT_COLLAB_FORM);
      const refreshed = await listWorkspaceCollaborationItems(selectedWorkspaceId, collaborationFilter === 'all' ? null : collaborationFilter);
      setCollaborationItems(refreshed.items || []);
      setCollaborationSummary(refreshed.summary || EMPTY_COLLAB_SUMMARY);
    } catch (err) {
      setCollaborationError(err instanceof Error ? err.message : 'Unable to save collaboration item.');
    } finally {
      setCollaborationActionLoading(false);
    }
  };

  const changeCollaborationStatus = async (item: WorkspaceCollaborationItem, nextStatus: string) => {
    if (!selectedWorkspaceId) return;
    setCollaborationActionLoading(true);
    setCollaborationError(null);
    try {
      await updateWorkspaceCollaborationItem(selectedWorkspaceId, item.collaboration_id, { status: nextStatus });
      const refreshed = await listWorkspaceCollaborationItems(selectedWorkspaceId, collaborationFilter === 'all' ? null : collaborationFilter);
      setCollaborationItems(refreshed.items || []);
      setCollaborationSummary(refreshed.summary || EMPTY_COLLAB_SUMMARY);
      setCollaborationMessage('Item status updated.');
    } catch (err) {
      setCollaborationError(err instanceof Error ? err.message : 'Unable to update item.');
    } finally {
      setCollaborationActionLoading(false);
    }
  };

  const removeCollaborationItem = async (item: WorkspaceCollaborationItem) => {
    if (!selectedWorkspaceId) return;
    const confirmDelete = window.confirm(`Delete ${item.title || item.item_type}?`);
    if (!confirmDelete) return;
    setCollaborationActionLoading(true);
    setCollaborationError(null);
    try {
      await deleteWorkspaceCollaborationItem(selectedWorkspaceId, item.collaboration_id);
      const refreshed = await listWorkspaceCollaborationItems(selectedWorkspaceId, collaborationFilter === 'all' ? null : collaborationFilter);
      setCollaborationItems(refreshed.items || []);
      setCollaborationSummary(refreshed.summary || EMPTY_COLLAB_SUMMARY);
      setCollaborationMessage('Item deleted.');
    } catch (err) {
      setCollaborationError(err instanceof Error ? err.message : 'Unable to delete item.');
    } finally {
      setCollaborationActionLoading(false);
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

  const filteredCollaborationItems =
    collaborationFilter === 'all'
      ? collaborationItems
      : collaborationItems.filter((item) => item.item_type === collaborationFilter);

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

      <div className="card">
        <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.85rem' }}>
          <div>
            <p className="label" style={{ marginBottom: '0.25rem' }}>Setup Journey</p>
            <strong style={{ fontSize: '1rem' }}>Workspace to source selection flow</strong>
            <p className="small-copy" style={{ marginTop: '0.3rem' }}>
              Create a workspace, attach data sources, choose the active source, then move into investigation.
            </p>
          </div>
          {activeWorkspace && (
            <span className="source-pill">
              Active: {activeWorkspace.workspace_name}
            </span>
          )}
        </div>

        <div className="grid-auto" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
          {setupSteps.map((step) => (
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

          <div className="card-sm" style={{ marginBottom: '1rem' }}>
            <div className="flex-between" style={{ flexWrap: 'wrap', gap: '0.75rem', marginBottom: '0.75rem' }}>
              <div>
                <p className="label" style={{ marginBottom: '0.25rem' }}>Collaboration Hub</p>
                <strong style={{ fontSize: '1rem' }}>Comments, mentions, tasks, and review notes</strong>
                <p className="small-copy" style={{ marginTop: '0.3rem' }}>
                  Keep decisions, review requests, and follow-up items attached to this workspace.
                </p>
              </div>
              <div className="flex-row" style={{ gap: '0.45rem', flexWrap: 'wrap' }}>
                {(['all', 'comment', 'task', 'review'] as const).map((itemType) => (
                  <button
                    key={itemType}
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => setCollaborationFilter(itemType)}
                    style={{
                      fontSize: '0.78rem',
                      borderColor: collaborationFilter === itemType ? 'rgba(79,70,229,0.35)' : undefined,
                      background: collaborationFilter === itemType ? 'rgba(79,70,229,0.08)' : undefined,
                    }}
                  >
                    {itemType === 'all' ? 'All items' : formatCollaborationLabel(itemType)}
                  </button>
                ))}
              </div>
            </div>

            {collaborationError && <FeedbackBanner title="Collaboration Error" message={collaborationError} variant="error" />}
            {collaborationMessage && <FeedbackBanner title="Status" message={collaborationMessage} variant="success" />}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
              <div className="card-sm">
                <p className="label">Total Items</p>
                <strong style={{ fontSize: '1.15rem' }}>{collaborationSummary.total_items}</strong>
              </div>
              <div className="card-sm">
                <p className="label">Open Items</p>
                <strong style={{ fontSize: '1.15rem' }}>{collaborationSummary.open_items}</strong>
              </div>
              <div className="card-sm">
                <p className="label">Completed</p>
                <strong style={{ fontSize: '1.15rem' }}>{collaborationSummary.completed_items}</strong>
              </div>
              <div className="card-sm">
                <p className="label">Mentions</p>
                <strong style={{ fontSize: '1.15rem' }}>{collaborationSummary.mention_count}</strong>
              </div>
            </div>

            <div className="grid-2" style={{ gap: '1rem', alignItems: 'start' }}>
              <div className="card-sm">
                <div className="flex-between" style={{ marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <p className="label" style={{ marginBottom: 0 }}>Workspace Feed</p>
                  <span className="source-pill">
                    {collaborationLoading ? 'Refreshing...' : `${filteredCollaborationItems.length} visible`}
                  </span>
                </div>

                {collaborationLoading ? (
                  <p className="body-copy">Loading collaboration items...</p>
                ) : filteredCollaborationItems.length === 0 ? (
                  <p className="body-copy">No collaboration items yet. Add a comment, task, or review note to start the workspace conversation.</p>
                ) : (
                  <div className="stack-sm">
                    {filteredCollaborationItems.map((item) => {
                      const isDone = Boolean(item.status && ['resolved', 'done', 'closed', 'approved'].includes(item.status.toLowerCase()));
                      return (
                        <div
                          key={item.collaboration_id}
                          className="card-sm"
                          style={{
                            borderLeft: `3px solid ${item.item_type === 'task' ? 'var(--accent-blue)' : item.item_type === 'review' ? 'var(--accent-purple)' : 'var(--accent-green)'}`,
                            background: 'rgba(255,255,255,0.92)',
                          }}
                        >
                          <div className="flex-between" style={{ gap: '0.75rem', alignItems: 'flex-start' }}>
                            <div style={{ minWidth: 0 }}>
                              <div className="flex-row" style={{ gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.35rem' }}>
                                <span className="source-pill">{formatCollaborationLabel(item.item_type)}</span>
                                {item.status && <span className="source-pill">{formatCollaborationLabel(item.status)}</span>}
                                {item.priority && <span className="source-pill">Priority: {formatCollaborationLabel(item.priority)}</span>}
                              </div>
                              <strong style={{ display: 'block', marginBottom: '0.2rem' }}>{item.title || 'Untitled item'}</strong>
                              <p className="body-copy" style={{ margin: 0 }}>{summarizeCollaborationItem(item)}</p>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem', marginTop: '0.6rem' }}>
                                {item.mentions.map((mention) => (
                                  <span key={`${item.collaboration_id}-${mention}`} className="source-pill">
                                    @{mention}
                                  </span>
                                ))}
                                {item.assignee_user_id && <span className="source-pill">Assignee: {item.assignee_user_id}</span>}
                                {item.due_date && <span className="source-pill">Due: {prettyDate(item.due_date)}</span>}
                              </div>
                            </div>
                            <div className="flex-row" style={{ gap: '0.45rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                              <button
                                type="button"
                                className="btn btn-ghost"
                                onClick={() => void changeCollaborationStatus(item, isDone ? 'open' : 'done')}
                                disabled={collaborationActionLoading}
                              >
                                {isDone ? 'Reopen' : 'Mark Done'}
                              </button>
                              <button
                                type="button"
                                className="btn btn-ghost"
                                onClick={() => void changeCollaborationStatus(item, 'resolved')}
                                disabled={collaborationActionLoading}
                              >
                                Resolve
                              </button>
                              <button
                                type="button"
                                className="btn btn-ghost"
                                onClick={() => void removeCollaborationItem(item)}
                                disabled={collaborationActionLoading}
                              >
                                Delete
                              </button>
                            </div>
                          </div>
                          <p className="small-copy" style={{ margin: '0.6rem 0 0' }}>
                            Updated {prettyDate(item.updated_at)}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="card-sm">
                <p className="label" style={{ marginBottom: '0.6rem' }}>Add Workspace Note</p>
                <div className="stack-sm">
                  <div className="grid-2" style={{ gap: '0.75rem' }}>
                    <label className="stack-sm" style={{ gap: '0.35rem' }}>
                      <span className="small-copy">Type</span>
                      <select
                        className="input"
                        value={collaborationForm.item_type}
                        onChange={(event) => updateCollaborationField('item_type', event.target.value as WorkspaceCollaborationItemType)}
                      >
                        <option value="comment">Comment</option>
                        <option value="task">Task</option>
                        <option value="review">Review</option>
                      </select>
                    </label>
                    <label className="stack-sm" style={{ gap: '0.35rem' }}>
                      <span className="small-copy">Status</span>
                      <input className="input" value={collaborationForm.status} onChange={(event) => updateCollaborationField('status', event.target.value)} placeholder="open / done / resolved" />
                    </label>
                  </div>

                  <label className="stack-sm" style={{ gap: '0.35rem' }}>
                    <span className="small-copy">Title</span>
                    <input
                      className="input"
                      value={collaborationForm.title}
                      onChange={(event) => updateCollaborationField('title', event.target.value)}
                      placeholder="Short title for this item"
                    />
                  </label>

                  <label className="stack-sm" style={{ gap: '0.35rem' }}>
                    <span className="small-copy">Body</span>
                    <textarea
                      className="input"
                      rows={4}
                      value={collaborationForm.body}
                      onChange={(event) => updateCollaborationField('body', event.target.value)}
                      placeholder="Write a comment, review note, or follow-up task"
                    />
                  </label>

                  <div className="grid-2" style={{ gap: '0.75rem' }}>
                    <label className="stack-sm" style={{ gap: '0.35rem' }}>
                      <span className="small-copy">Priority</span>
                      <select
                        className="input"
                        value={collaborationForm.priority}
                        onChange={(event) => updateCollaborationField('priority', event.target.value)}
                      >
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                      </select>
                    </label>
                    <label className="stack-sm" style={{ gap: '0.35rem' }}>
                      <span className="small-copy">Due Date</span>
                      <input
                        className="input"
                        type="date"
                        value={collaborationForm.due_date}
                        onChange={(event) => updateCollaborationField('due_date', event.target.value)}
                      />
                    </label>
                  </div>

                  <label className="stack-sm" style={{ gap: '0.35rem' }}>
                    <span className="small-copy">Mentions</span>
                    <input
                      className="input"
                      value={collaborationForm.mentions_text}
                      onChange={(event) => updateCollaborationField('mentions_text', event.target.value)}
                      placeholder="team.member, reviewer.name"
                    />
                  </label>

                  <label className="stack-sm" style={{ gap: '0.35rem' }}>
                    <span className="small-copy">Assignee User ID</span>
                    <input
                      className="input"
                      value={collaborationForm.assignee_user_id}
                      onChange={(event) => updateCollaborationField('assignee_user_id', event.target.value)}
                      placeholder="Optional user identifier"
                    />
                  </label>

                  <div className="flex-row" style={{ gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button className="btn btn-primary" type="button" onClick={() => void saveCollaborationItem()} disabled={collaborationActionLoading}>
                      Save Item
                    </button>
                    <button
                      className="btn btn-secondary"
                      type="button"
                      onClick={() => setCollaborationForm(DEFAULT_COLLAB_FORM)}
                      disabled={collaborationActionLoading}
                    >
                      Reset
                    </button>
                  </div>
                </div>
              </div>
            </div>
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

