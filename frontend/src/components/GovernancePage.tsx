import { useEffect, useMemo, useState } from 'react';
import { AdminDashboard } from './AdminDashboard';
import { DatabaseConnectionsPage } from './DatabaseConnectionsPage';
import { MetricCard } from './MetricCard';
import { RecentInvestigations } from './RecentInvestigations';
import { SystemOverview } from './SystemOverview';
import { WorkspaceManagementPage } from './WorkspaceManagementPage';
import { listAdminUsers, listGovernanceAuditEventsWithFilters } from '../services/adminApi';
import type { AuthUser } from '../types/auth';
import type { GovernanceAuditRecord } from '../types/audit';

type GovernanceSection = 'overview' | 'users' | 'workspaces' | 'sources' | 'policies' | 'activity';

interface GovernancePageProps {
  isAdmin: boolean;
  currentUserId: string;
}

type ActivityCardItem = {
  id: string;
  title: string;
  detail: string;
  meta?: string;
  time: string;
  level: 'success' | 'warning' | 'info';
};

const FALLBACK_ACTIVITY: ActivityCardItem[] = [
  { id: 'fallback-1', title: 'Source activated', detail: 'Database1 was marked as the active source for the current workspace.', time: '12 min ago', level: 'success' },
  { id: 'fallback-2', title: 'Workspace updated', detail: 'Audit Workspace was refreshed with a new source selection.', time: '34 min ago', level: 'info' },
  { id: 'fallback-3', title: 'User status reviewed', detail: 'An admin account was checked against RBAC rules before update.', time: '1 hr ago', level: 'warning' },
  { id: 'fallback-4', title: 'Connection tested', detail: 'PostgreSQL connection validation completed successfully.', time: '2 hr ago', level: 'success' },
];

const SECTION_COPY: Record<GovernanceSection, { title: string; description: string }> = {
  overview: {
    title: 'Governance Overview',
    description: 'Track the control plane for users, workspaces, and data sources from one place.',
  },
  users: {
    title: 'Users & Roles',
    description: 'Review users, roles, and account state for admin governance.',
  },
  workspaces: {
    title: 'Workspaces',
    description: 'Manage source scope, active workspace selection, and investigation context.',
  },
  sources: {
    title: 'Sources',
    description: 'Add, test, and activate database connections used by the audit assistant.',
  },
  policies: {
    title: 'Policies',
    description: 'Review access rules, source governance rules, and workspace guardrails.',
  },
  activity: {
    title: 'Governance Activity',
    description: 'Review recent governance actions, source events, and workspace updates.',
  },
};

export function GovernancePage({ isAdmin, currentUserId }: GovernancePageProps) {
  const [section, setSection] = useState<GovernanceSection>('overview');
  const [activityEvents, setActivityEvents] = useState<GovernanceAuditRecord[]>([]);
  const [adminUsers, setAdminUsers] = useState<AuthUser[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [activitySearch, setActivitySearch] = useState('');
  const [activitySeverity, setActivitySeverity] = useState('');
  const [activityAction, setActivityAction] = useState('');
  const [activityUserId, setActivityUserId] = useState('');
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  const sectionItems = useMemo(
    () => ([
      ['overview', 'Overview'],
      ['users', 'Users & Roles'],
      ['workspaces', 'Workspaces'],
      ['sources', 'Sources'],
      ['policies', 'Policies'],
      ['activity', 'Activity'],
    ] as const),
    [],
  );

  useEffect(() => {
    if (section !== 'activity') {
      return;
    }
    let cancelled = false;
    setActivityLoading(true);
    setActivityError(null);
    const actorUserId = isAdmin ? activityUserId || undefined : currentUserId || undefined;
    Promise.all([
      listGovernanceAuditEventsWithFilters({
        limit: 30,
        search: activitySearch.trim() || undefined,
        severity: activitySeverity || undefined,
        action_type: activityAction || undefined,
        actor_user_id: actorUserId,
      }),
      isAdmin ? listAdminUsers() : Promise.resolve([] as AuthUser[]),
    ])
      .then(([events, users]) => {
        if (!cancelled) {
          setActivityEvents(events);
          setAdminUsers(users);
          setSelectedEventId((current) => current && events.some((event) => event.audit_log_id === current) ? current : events[0]?.audit_log_id ?? null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setActivityError(error instanceof Error ? error.message : 'Failed to load governance activity.');
          setActivityEvents([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setActivityLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activityAction, activitySearch, activitySeverity, activityUserId, currentUserId, isAdmin, section]);

  const renderedActivity: ActivityCardItem[] = activityEvents.length > 0
    ? activityEvents.map((event) => ({
      id: event.audit_log_id,
      title: event.action_type.replace(/_/g, ' ').replace(/\b\w/g, (char: string) => char.toUpperCase()),
      detail: event.summary,
      meta: [
        event.actor_name || event.actor_user_id || 'System',
        event.entity_type ? `Entity: ${event.entity_type}` : null,
      ].filter(Boolean).join(' • '),
      time: formatRelativeTime(event.created_at),
      level: event.severity === 'warning' || event.severity === 'error' ? 'warning' : 'success',
    }))
    : FALLBACK_ACTIVITY;
  const selectedEvent = selectedEventId ? activityEvents.find((event) => event.audit_log_id === selectedEventId) || null : null;
  const activeUsers = useMemo(() => {
    if (!isAdmin) {
      return [];
    }
    const cutoff = Date.now() - 15 * 60 * 1000;
    const recent = new Map<string, { name: string; lastSeen: number }>();
    for (const event of activityEvents) {
      const eventTime = Date.parse(event.created_at);
      if (Number.isNaN(eventTime) || eventTime < cutoff) {
        continue;
      }
      const id = event.actor_user_id || event.actor_name || 'system';
      const name = event.actor_name || event.actor_user_id || 'System';
      const existing = recent.get(id);
      if (!existing || eventTime > existing.lastSeen) {
        recent.set(id, { name, lastSeen: eventTime });
      }
    }
    return Array.from(recent.entries())
      .sort((left, right) => right[1].lastSeen - left[1].lastSeen)
      .map(([id, value]) => ({ id, name: value.name, lastSeen: value.lastSeen }));
  }, [activityEvents]);
  const activityStats = useMemo(() => {
    const totalEvents = activityEvents.length;
    const uniqueActors = new Set(
      activityEvents.map((event) => event.actor_user_id || event.actor_name || 'system'),
    ).size;
    const elevatedEvents = activityEvents.filter((event) => event.severity === 'warning' || event.severity === 'error').length;
    const latestTimestamp = activityEvents.reduce<number | null>((latest, event) => {
      const timestamp = Date.parse(event.created_at);
      if (Number.isNaN(timestamp)) {
        return latest;
      }
      return latest === null || timestamp > latest ? timestamp : latest;
    }, null);
    return {
      totalEvents,
      uniqueActors,
      elevatedEvents,
      latestTimestamp,
    };
  }, [activityEvents]);
  const activityUserOptions = useMemo(() => {
    if (!isAdmin) {
      return [];
    }
    const options = new Map<string, string>();
    for (const user of adminUsers) {
      options.set(user.user_id, user.full_name || user.email);
    }
    for (const event of activityEvents) {
      if (event.actor_user_id) {
        options.set(event.actor_user_id, event.actor_name || event.actor_user_id);
      }
    }
    return Array.from(options.entries()).sort((left, right) => left[1].localeCompare(right[1]));
  }, [adminUsers, activityEvents, isAdmin]);
  const handleExportActivity = () => {
    if (activityEvents.length === 0) {
      return;
    }
    const blob = new Blob([JSON.stringify(activityEvents, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'governance-audit-events.json';
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="stack" style={{ gap: '1.25rem' }}>
      <div className="card">
        <p className="eyebrow" style={{ marginBottom: '0.35rem' }}>Governance</p>
        <h1 style={{ fontSize: '1.65rem', fontWeight: 800 }}>{SECTION_COPY[section].title}</h1>
        <p className="body-copy" style={{ marginTop: '0.35rem', maxWidth: '72ch' }}>
          {SECTION_COPY[section].description}
        </p>
      </div>

      <div className="tab-bar" style={{ flexWrap: 'wrap' }}>
        {sectionItems.map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`tab-btn${section === key ? ' active' : ''}`}
            onClick={() => setSection(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {section === 'overview' && (
        <div className="stack" style={{ gap: '1rem' }}>
          <div className="grid-auto" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))' }}>
            <MetricCard label="Governance Controls" value="4" detail="Users, workspaces, sources, and activity." trend="+1 section" trendDirection="up" accent="#38bdf8" />
            <MetricCard label="Admin Ready" value={isAdmin ? 'Yes' : 'No'} detail="RBAC is enforced for privileged actions." trend={isAdmin ? 'Admin session active' : 'User session active'} trendDirection="flat" accent="#a78bfa" />
            <MetricCard label="Workspace Scope" value="Active" detail="Selected source context is applied to investigations." trend="Auto-applied" trendDirection="up" accent="#34d399" />
            <MetricCard label="Source Health" value="Monitored" detail="Connection testing and source selection are available." trend="Validated sources visible" trendDirection="flat" accent="#f59e0b" />
          </div>

          <div className="grid-2" style={{ gap: '1rem', alignItems: 'start' }}>
            <SystemOverview />
            <RecentInvestigations />
          </div>

          <div className="grid-2" style={{ gap: '1rem', alignItems: 'start' }}>
            <div className="card">
              <p className="label" style={{ marginBottom: '0.5rem' }}>Governance Workflow</p>
              <div className="stack-sm">
                <div className="card-sm"><strong>1. Users & Roles</strong><p className="small-copy">Control who can access the platform and what actions they can take.</p></div>
                <div className="card-sm"><strong>2. Workspaces</strong><p className="small-copy">Scope investigations to the correct data sources and contexts.</p></div>
                <div className="card-sm"><strong>3. Sources</strong><p className="small-copy">Manage database connectivity, testing, and active source selection.</p></div>
                <div className="card-sm"><strong>4. Activity</strong><p className="small-copy">Review the governance trail for user, source, and workspace actions.</p></div>
              </div>
            </div>
            <div className="card">
              <p className="label" style={{ marginBottom: '0.5rem' }}>Admin Quick Actions</p>
              <div className="stack-sm">
                <div className="card-sm">
                  <strong>Open User Controls</strong>
                  <p className="small-copy">Inspect user status and RBAC controls for this session.</p>
                </div>
                <div className="card-sm">
                  <strong>Open Workspace Manager</strong>
                  <p className="small-copy">Choose which workspace and sources scope the audit assistant.</p>
                </div>
                <div className="card-sm">
                  <strong>Open Source Console</strong>
                  <p className="small-copy">Add or test a database connection before using it in investigations.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {section === 'users' && (
        <div className="card">
          {isAdmin ? (
            <AdminDashboard
              onOpenConnections={() => setSection('sources')}
              onOpenWorkspaces={() => setSection('workspaces')}
              currentUserId={currentUserId}
            />
          ) : (
            <div className="stack-sm">
              <p className="label">Access Restricted</p>
              <p className="body-copy">User and role governance is available to admin users only.</p>
            </div>
          )}
        </div>
      )}

      {section === 'workspaces' && (
        <div className="card">
          <WorkspaceManagementPage />
        </div>
      )}

      {section === 'sources' && (
        <div className="card">
          <DatabaseConnectionsPage isAdminView={isAdmin} />
        </div>
      )}

      {section === 'activity' && (
        <div className="stack" style={{ gap: '1rem' }}>
          <div className="grid-auto" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))' }}>
            <MetricCard
              label="Activity Events"
              value={String(activityStats.totalEvents || 0)}
              detail="Governance, source, workspace, and user actions in view."
              trend={isAdmin ? 'Admin-wide feed' : 'Personal activity feed'}
              trendDirection="flat"
              accent="#38bdf8"
            />
            <MetricCard
              label={isAdmin ? 'Active Users' : 'Activity Scope'}
              value={isAdmin ? String(activeUsers.length || 0) : 'Self only'}
              detail={isAdmin ? 'Recent active users in the last 15 minutes.' : 'Non-admin users can only review their own actions.'}
              trend={isAdmin ? 'Live monitoring' : 'Restricted view'}
              trendDirection="flat"
              accent="#34d399"
            />
            <MetricCard
              label="Elevated Events"
              value={String(activityStats.elevatedEvents || 0)}
              detail="Warnings and errors across the governance trail."
              trend={activityStats.elevatedEvents > 0 ? 'Needs review' : 'No escalations'}
              trendDirection={activityStats.elevatedEvents > 0 ? 'up' : 'flat'}
              accent="#f59e0b"
            />
            <MetricCard
              label="Latest Update"
              value={activityStats.latestTimestamp ? formatRelativeTime(new Date(activityStats.latestTimestamp).toISOString()) : '—'}
              detail={activityStats.latestTimestamp ? new Date(activityStats.latestTimestamp).toLocaleString() : 'No recent activity recorded.'}
              trend={activityStats.uniqueActors > 0 ? `${activityStats.uniqueActors} actor${activityStats.uniqueActors === 1 ? '' : 's'}` : 'No actors'}
              trendDirection="flat"
              accent="#a78bfa"
            />
          </div>

          {isAdmin && (
            <div className="card">
              <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.65rem' }}>
                <p className="label">Active Now</p>
                <span className="badge badge-completed">{activeUsers.length} active user{activeUsers.length === 1 ? '' : 's'}</span>
              </div>
              <div className="flex-row" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
                {activeUsers.length > 0 ? activeUsers.map((user) => (
                  <span key={user.id} className="source-pill">
                    {user.name}
                  </span>
                )) : (
                  <p className="small-copy">No users are active right now.</p>
                )}
              </div>
            </div>
          )}

          <div className="grid-2" style={{ gap: '1rem', alignItems: 'start' }}>
            <div className="card">
              <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.65rem' }}>
                <p className="label">Audit Trail</p>
                <button type="button" className="tab-btn" onClick={handleExportActivity} disabled={activityEvents.length === 0}>
                  Export
                </button>
              </div>
              <div className="grid-3" style={{ gap: '0.6rem', marginBottom: '0.85rem' }}>
                <input
                  value={activitySearch}
                  onChange={(event) => setActivitySearch(event.target.value)}
                  placeholder="Search activity"
                  className="input"
                />
                {isAdmin ? (
                  <select value={activityUserId} onChange={(event) => setActivityUserId(event.target.value)} className="input">
                    <option value="">All users</option>
                    {activityUserOptions.map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                ) : (
                  <div className="card-sm" style={{ alignSelf: 'stretch' }}>
                    <strong>My activity only</strong>
                    <p className="small-copy">Non-admin users can review only their own governance trail.</p>
                  </div>
                )}
                <select value={activitySeverity} onChange={(event) => setActivitySeverity(event.target.value)} className="input">
                  <option value="">All severities</option>
                  <option value="info">Info</option>
                  <option value="warning">Warning</option>
                  <option value="error">Error</option>
                </select>
              </div>
              <div className="grid-3" style={{ gap: '0.6rem', marginBottom: '0.85rem' }}>
                <select value={activityAction} onChange={(event) => setActivityAction(event.target.value)} className="input">
                  <option value="">All actions</option>
                  <option value="signup_completed">Signup Completed</option>
                  <option value="signup_failed">Signup Failed</option>
                  <option value="login_completed">Login Completed</option>
                  <option value="login_failed">Login Failed</option>
                  <option value="google_login_completed">Google Login Completed</option>
                  <option value="chat_turn_started">Chat Turn Started</option>
                  <option value="chat_turn_completed">Chat Turn Completed</option>
                  <option value="audit_query_started">Audit Query Started</option>
                  <option value="audit_query_completed">Audit Query Completed</option>
                  <option value="audit_query_failed">Audit Query Failed</option>
                  <option value="audit_query_rejected">Audit Query Rejected</option>
                  <option value="workspace_created">Workspace Created</option>
                  <option value="workspace_updated">Workspace Updated</option>
                  <option value="workspace_activated">Workspace Activated</option>
                  <option value="workspace_deleted">Workspace Deleted</option>
                  <option value="connection_tested">Connection Tested</option>
                  <option value="connection_created">Connection Created</option>
                  <option value="connection_updated">Connection Updated</option>
                  <option value="connection_activated">Connection Activated</option>
                  <option value="connection_deleted">Connection Deleted</option>
                  <option value="user_status_updated">User Status Updated</option>
                  <option value="admin_self_deactivation_blocked">Self-Deactivation Blocked</option>
                </select>
              </div>
              {activityLoading && <p className="small-copy">Loading governance activity...</p>}
              {!isAdmin && !activityLoading && (
                <div className="card-sm" style={{ marginBottom: '0.75rem' }}>
                  <strong>Personal activity stream</strong>
                  <p className="small-copy" style={{ marginTop: '0.35rem' }}>
                    You are viewing your own governance actions, query activity, and source operations.
                  </p>
                </div>
              )}
              {activityError && (
                <div className="card-sm" style={{ marginBottom: '0.75rem' }}>
                  <strong>Activity feed unavailable</strong>
                  <p className="small-copy" style={{ marginTop: '0.35rem' }}>{activityError}</p>
                </div>
              )}
              <div className="stack-sm">
                {renderedActivity.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`card-sm${selectedEventId === item.id ? ' active' : ''}`}
                    onClick={() => {
                      setSelectedEventId(item.id);
                    }}
                    style={{ textAlign: 'left' }}
                  >
                    <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
                      <strong>{item.title}</strong>
                      <span className={`badge ${item.level === 'success' ? 'badge-completed' : item.level === 'warning' ? 'badge-failed' : 'badge-completed'}`}>
                        {item.time}
                      </span>
                    </div>
                    <p className="small-copy" style={{ marginTop: '0.35rem' }}>{item.detail}</p>
                    {'meta' in item && item.meta && (
                      <p className="small-copy" style={{ marginTop: '0.25rem', opacity: 0.82 }}>{item.meta}</p>
                    )}
                  </button>
                ))}
              </div>
            </div>

            <div className="card">
              <p className="label" style={{ marginBottom: '0.65rem' }}>Event Details</p>
              {selectedEvent ? (
                <div className="stack-sm">
                  <div className="card-sm">
                    <strong>{formatActionLabel(selectedEvent.action_type)}</strong>
                    <p className="small-copy" style={{ marginTop: '0.35rem' }}>{selectedEvent.summary}</p>
                  </div>
                  <div className="grid-2" style={{ gap: '0.6rem' }}>
                    <InfoTile label="Actor" value={selectedEvent.actor_name || selectedEvent.actor_user_id || 'System'} />
                    <InfoTile label="Severity" value={selectedEvent.severity} />
                    <InfoTile label="Entity" value={selectedEvent.entity_type} />
                    <InfoTile label="Time" value={new Date(selectedEvent.created_at).toLocaleString()} />
                  </div>
                  <div className="card-sm">
                    <p className="label">Linked Context</p>
                    <div className="stack-sm" style={{ marginTop: '0.5rem' }}>
                      <InfoTile label="Entity ID" value={selectedEvent.entity_id || '—'} />
                      <InfoTile label="Workspace" value={selectedEvent.workspace_id || '—'} />
                      <InfoTile label="Connection" value={selectedEvent.connection_id || '—'} />
                    </div>
                  </div>
                  <div className="card-sm">
                    <p className="label">State Before</p>
                    <pre className="small-copy" style={{ whiteSpace: 'pre-wrap', marginTop: '0.35rem' }}>{formatObject(selectedEvent.before_state)}</pre>
                  </div>
                  <div className="card-sm">
                    <p className="label">State After</p>
                    <pre className="small-copy" style={{ whiteSpace: 'pre-wrap', marginTop: '0.35rem' }}>{formatObject(selectedEvent.after_state)}</pre>
                  </div>
                </div>
              ) : (
                <div className="stack-sm">
                  <div className="card-sm"><strong>No event selected</strong><p className="small-copy">Choose a governance event to inspect the full details.</p></div>
                  <div className="card-sm"><strong>Governance Notes</strong><p className="small-copy">Admin-only actions stay protected inside the governance workflow.</p></div>
                  <div className="card-sm"><strong>Source Control</strong><p className="small-copy">Connection testing messages now surface in clean human language.</p></div>
                  <div className="card-sm"><strong>Traceability</strong><p className="small-copy">Governance actions can be linked to future audit logging and execution metadata.</p></div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {section === 'policies' && (
        <div className="grid-2" style={{ gap: '1rem', alignItems: 'start' }}>
          <div className="card">
            <p className="label" style={{ marginBottom: '0.65rem' }}>Policy Controls</p>
            <div className="stack-sm">
              <div className="card-sm">
                <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
                  <strong>Admin Self-Protection</strong>
                  <span className="badge badge-completed">Enabled</span>
                </div>
                <p className="small-copy" style={{ marginTop: '0.35rem' }}>
                  Admin users cannot deactivate their own account.
                </p>
              </div>
              <div className="card-sm">
                <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
                  <strong>Source Access Scope</strong>
                  <span className="badge badge-completed">Workspace-bound</span>
                </div>
                <p className="small-copy" style={{ marginTop: '0.35rem' }}>
                  Selected sources follow the active workspace for each investigation.
                </p>
              </div>
              <div className="card-sm">
                <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
                  <strong>Connection Validation</strong>
                  <span className="badge badge-completed">Required</span>
                </div>
                <p className="small-copy" style={{ marginTop: '0.35rem' }}>
                  New sources must pass connection testing before being saved.
                </p>
              </div>
              <div className="card-sm">
                <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
                  <strong>Audit Trail</strong>
                  <span className="badge badge-completed">On</span>
                </div>
                <p className="small-copy" style={{ marginTop: '0.35rem' }}>
                  Governance actions are ready to be linked to audit logging.
                </p>
              </div>
            </div>
          </div>

          <div className="card">
            <p className="label" style={{ marginBottom: '0.65rem' }}>Policy Summary</p>
            <div className="stack-sm">
              <div className="card-sm">
                <strong>Who can change sources?</strong>
                <p className="small-copy">Admins manage source creation, testing, and activation.</p>
              </div>
              <div className="card-sm">
                <strong>How is scope applied?</strong>
                <p className="small-copy">The active workspace determines which source and schema context the assistant uses.</p>
              </div>
              <div className="card-sm">
                <strong>What is protected?</strong>
                <p className="small-copy">Admin self-deactivation and invalid connection states are blocked.</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function formatActionLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char: string) => char.toUpperCase());
}

function formatObject(value: Record<string, unknown> | null | undefined): string {
  if (!value || Object.keys(value).length === 0) {
    return '—';
  }
  return JSON.stringify(value, null, 2);
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="card-sm">
      <p className="label" style={{ marginBottom: '0.25rem' }}>{label}</p>
      <p className="small-copy">{value}</p>
    </div>
  );
}

function formatRelativeTime(value: string): string {
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return 'just now';
  }
  const diffMinutes = Math.max(0, Math.round((Date.now() - timestamp) / 60000));
  if (diffMinutes < 1) return 'just now';
  if (diffMinutes < 60) return `${diffMinutes} min ago`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} hr ago`;
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
}
