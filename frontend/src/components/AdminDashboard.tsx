import { useEffect, useMemo, useState } from 'react';
import { listAdminConnections, listAdminUsers, listAdminWorkspaces, updateAdminUserStatus } from '../services/adminApi';
import type { AuthUser } from '../types/auth';
import type { DatabaseConnectionRecord } from '../types/databaseConnections';
import type { WorkspaceRecord } from '../types/workspace';
import { FeedbackBanner } from './FeedbackBanner';

interface AdminDashboardProps {
  onOpenConnections: () => void;
  onOpenWorkspaces: () => void;
  currentUserId: string;
}

function prettyDate(value?: string | null) {
  if (!value) return 'n/a';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function statusLabel(value?: string | null) {
  if (!value) return 'Unknown';
  return value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="kpi-card">
      <p className="label">{label}</p>
      <div className="kpi-value">{value}</div>
      <p className="body-copy">{detail}</p>
    </div>
  );
}

export function AdminDashboard({ onOpenConnections, onOpenWorkspaces, currentUserId }: AdminDashboardProps) {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceRecord[]>([]);
  const [connections, setConnections] = useState<DatabaseConnectionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([listAdminUsers(), listAdminWorkspaces(), listAdminConnections()])
      .then(([userItems, workspaceItems, connectionItems]) => {
        if (!active) return;
        setUsers(userItems);
        setWorkspaces(workspaceItems);
        setConnections(connectionItems);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Unable to load admin dashboard data.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const metrics = useMemo(() => {
    const adminUsers = users.filter((user) => user.role === 'admin').length;
    const activeUsers = users.filter((user) => user.is_active).length;
    const activeConnections = connections.filter((connection) => connection.is_active).length;
    const defaultWorkspaces = workspaces.filter((workspace) => workspace.is_default).length;
    const testedConnections = connections.filter((connection) => connection.last_test_status === 'passed').length;
    return [
      { label: 'Total Users', value: String(users.length), detail: `${adminUsers} admin account(s) registered.` },
      { label: 'Active Users', value: String(activeUsers), detail: `${users.length - activeUsers} account(s) currently inactive.` },
      { label: 'Workspaces', value: String(workspaces.length), detail: `${defaultWorkspaces} workspace(s) marked as default.` },
      { label: 'Saved Sources', value: String(connections.length), detail: `${activeConnections} source(s) currently active.` },
      { label: 'Validated Sources', value: String(testedConnections), detail: 'Sources that passed their last connection test.' },
    ];
  }, [connections, users, workspaces]);

  const recentUsers = useMemo(() => users.slice(0, 5), [users]);
  const recentWorkspaces = useMemo(() => workspaces.slice(0, 5), [workspaces]);
  const recentConnections = useMemo(() => connections.slice(0, 5), [connections]);

  const handleToggleUserActive = async (user: AuthUser) => {
    setUpdatingUserId(user.user_id);
    setError(null);
    setNotice(null);
    try {
      const updatedUser = await updateAdminUserStatus(user.user_id, !user.is_active);
      setUsers((current) => current.map((item) => (item.user_id === updatedUser.user_id ? updatedUser : item)));
      setNotice(`${updatedUser.full_name} is now ${updatedUser.is_active ? 'active' : 'inactive'}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update user status.');
    } finally {
      setUpdatingUserId(null);
    }
  };

  return (
    <div className="stack" style={{ gap: '1.25rem' }}>
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow" style={{ marginBottom: '0.5rem' }}>Administration</p>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '0.5rem' }}>
            Admin Control Center
          </h1>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '60ch', lineHeight: 1.6 }}>
            Review users, workspaces, and data sources from a single executive view. Use this area to understand who is
            active, which workspaces are in use, and how the connected sources are performing.
          </p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', flexShrink: 0 }}>
          <button className="btn btn-primary" onClick={onOpenConnections} style={{ padding: '0.75rem 1.5rem', fontSize: '0.95rem' }}>
            Open Source Console
          </button>
          <button className="btn btn-secondary" onClick={onOpenWorkspaces} style={{ padding: '0.75rem 1.5rem', fontSize: '0.95rem' }}>
            Open Workspace Manager
          </button>
        </div>
      </div>

      {error && <FeedbackBanner title="Admin Dashboard Error" message={error} variant="error" />}

      {notice && <FeedbackBanner title="Update Complete" message={notice} variant="success" />}

      <div className="grid-auto" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))' }}>
        {metrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </div>

      <div className="grid-3" style={{ gap: '1rem', alignItems: 'start' }}>
        <div className="card">
          <p className="label" style={{ marginBottom: '0.75rem' }}>Recent Users</p>
          <div className="stack-sm">
            {loading ? (
              <p className="body-copy">Loading users...</p>
            ) : recentUsers.length === 0 ? (
              <p className="body-copy">No users available.</p>
            ) : (
              recentUsers.map((user) => (
                <div key={user.user_id} className="card-sm">
                  <div className="flex-between" style={{ alignItems: 'flex-start' }}>
                    <div>
                      <strong>{user.full_name}</strong>
                      <p className="small-copy">{user.email}</p>
                      <p className="small-copy">Provider: {user.auth_provider}</p>
                      <p className="small-copy">Role: {user.role || 'user'}</p>
                    </div>
                    <div style={{ display: 'grid', justifyItems: 'end', gap: '0.4rem' }}>
                      <span className={user.role === 'admin' ? 'source-pill' : 'badge badge-completed'}>
                        {user.role || 'user'}
                      </span>
                      <span className={user.is_active ? 'badge badge-completed' : 'badge badge-failed'}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  </div>
                  <div className="flex-between" style={{ marginTop: '0.65rem', alignItems: 'center', flexWrap: 'wrap' }}>
                    <p className="small-copy">Last login: {prettyDate(user.last_login_at)}</p>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={() => handleToggleUserActive(user)}
                        disabled={updatingUserId === user.user_id || user.user_id === currentUserId}
                      >
                      {user.user_id === currentUserId ? 'Current User' : user.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </div>
                  </div>
              ))
            )}
          </div>
        </div>

        <div className="card">
          <p className="label" style={{ marginBottom: '0.75rem' }}>Recent Workspaces</p>
          <div className="stack-sm">
            {loading ? (
              <p className="body-copy">Loading workspaces...</p>
            ) : recentWorkspaces.length === 0 ? (
              <p className="body-copy">No workspaces available.</p>
            ) : (
              recentWorkspaces.map((workspace) => (
                <div key={workspace.workspace_id} className="card-sm">
                  <strong>{workspace.workspace_name}</strong>
                  <p className="small-copy">{workspace.description || 'No description provided.'}</p>
                  <p className="small-copy">
                    Active source: {workspace.active_connection_id || workspace.selected_connection_ids[0] || 'not set'}
                  </p>
                  <div className="flex-row" style={{ marginTop: '0.5rem', flexWrap: 'wrap' }}>
                    {workspace.is_default ? <span className="source-pill">Default</span> : null}
                    {workspace.is_active ? <span className="badge badge-completed">Active</span> : null}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="card">
          <p className="label" style={{ marginBottom: '0.75rem' }}>Recent Sources</p>
          <div className="stack-sm">
            {loading ? (
              <p className="body-copy">Loading sources...</p>
            ) : recentConnections.length === 0 ? (
              <p className="body-copy">No sources available.</p>
            ) : (
              recentConnections.map((connection) => (
                <div key={connection.connection_id} className="card-sm">
                  <strong>{connection.connection_name}</strong>
                  <p className="small-copy">
                    {connection.database_type.toUpperCase()} | {connection.host}:{connection.port} | {connection.database_name}
                  </p>
                  <p className="small-copy">Last test: {statusLabel(connection.last_test_status)}</p>
                  <p className="small-copy">Tested: {prettyDate(connection.last_tested_at)}</p>
                  <div className="flex-row" style={{ marginTop: '0.5rem', flexWrap: 'wrap' }}>
                    {connection.is_default ? <span className="source-pill">Active</span> : null}
                    {connection.is_active ? <span className="badge badge-completed">Enabled</span> : null}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
