import { useEffect, useMemo, useState } from 'react';
import { AdminDashboard } from './AdminDashboard';
import { MetricCard } from './MetricCard';
import { RecentInvestigations } from './RecentInvestigations';
import { SystemOverview } from './SystemOverview';
import { getRouterReviewSummary, listActiveUsers, listAdminUsers, listGovernanceAuditEventsWithFilters } from '../services/adminApi';
import type { ActiveUserRecord } from '../services/adminApi';
import type { AuthUser } from '../types/auth';
import type { GovernanceAuditRecord, RouterReviewSummaryResponse } from '../types/audit';

type GovernanceSection = 'overview' | 'users' | 'policies' | 'activity';

interface GovernancePageProps {
  isAdmin: boolean;
  currentUserId: string;
  realtimeTick?: number;
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
    description: 'Track the control plane for users, roles, policies, and activity from one place.',
  },
  users: {
    title: 'Users & Roles',
    description: 'Review users, roles, and account state for admin governance.',
  },
  policies: {
    title: 'Policies',
    description: 'Review access rules and governance guardrails.',
  },
  activity: {
    title: 'Governance Activity',
    description: 'Review recent governance actions and admin activity.',
  },
};

export function GovernancePage({ isAdmin, currentUserId, realtimeTick = 0 }: GovernancePageProps) {
  const [section, setSection] = useState<GovernanceSection>('overview');
  const [activityEvents, setActivityEvents] = useState<GovernanceAuditRecord[]>([]);
  const [adminUsers, setAdminUsers] = useState<AuthUser[]>([]);
  const [activeUsers, setActiveUsers] = useState<ActiveUserRecord[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [activitySearch, setActivitySearch] = useState('');
  const [activitySeverity, setActivitySeverity] = useState('');
  const [activityAction, setActivityAction] = useState('');
  const [activityUserId, setActivityUserId] = useState('');
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [routerSummary, setRouterSummary] = useState<RouterReviewSummaryResponse | null>(null);
  const [routerSummaryLoading, setRouterSummaryLoading] = useState(false);
  const [routerSummaryError, setRouterSummaryError] = useState<string | null>(null);

  const sectionItems = useMemo(
    () => ([
      ['overview', 'Overview'],
      ['users', 'Users & Roles'],
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
    setRouterSummaryLoading(true);
    setActivityError(null);
    setRouterSummaryError(null);
    const actorUserId = isAdmin ? activityUserId || undefined : currentUserId || undefined;
    Promise.all([
      listGovernanceAuditEventsWithFilters({
        limit: 30,
        search: activitySearch.trim() || undefined,
        severity: activitySeverity || undefined,
        action_type: activityAction || undefined,
        actor_user_id: actorUserId,
      }),
      getRouterReviewSummary({
        limit: 200,
        severity: activitySeverity || undefined,
        actor_user_id: actorUserId,
      }),
      isAdmin ? listAdminUsers() : Promise.resolve([] as AuthUser[]),
    ])
      .then(([events, routerSummaryResponse, users]) => {
        if (!cancelled) {
          setActivityEvents(events);
          setRouterSummary(routerSummaryResponse);
          setAdminUsers(users);
          setSelectedEventId((current) => current && events.some((event) => event.audit_log_id === current) ? current : events[0]?.audit_log_id ?? null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setActivityError(error instanceof Error ? error.message : 'Failed to load governance activity.');
          setRouterSummaryError(error instanceof Error ? error.message : 'Failed to load router review summary.');
          setActivityEvents([]);
          setRouterSummary(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setActivityLoading(false);
          setRouterSummaryLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activityAction, activitySearch, activitySeverity, activityUserId, currentUserId, isAdmin, section, realtimeTick]);

  useEffect(() => {
    if (!isAdmin) {
      setActiveUsers([]);
      return;
    }
    let cancelled = false;
    listActiveUsers()
      .then((items) => {
        if (!cancelled) {
          setActiveUsers(items);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setActiveUsers([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [isAdmin, realtimeTick]);

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
            <MetricCard label="Governance Controls" value="4" detail="Users, roles, policies, and activity." trend="+1 section" trendDirection="up" accent="#38bdf8" />
            <MetricCard label="Admin Ready" value={isAdmin ? 'Yes' : 'No'} detail="RBAC is enforced for privileged actions." trend={isAdmin ? 'Admin session active' : 'User session active'} trendDirection="flat" accent="#a78bfa" />
            <MetricCard label="Policy Scope" value="Active" detail="Governance policies apply across users and sessions." trend="Auto-applied" trendDirection="up" accent="#34d399" />
            <MetricCard label="Activity Health" value="Monitored" detail="Connection testing and governance activity are available." trend="Validated actions visible" trendDirection="flat" accent="#f59e0b" />
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
                <div className="card-sm"><strong>2. Policies</strong><p className="small-copy">Define and review guardrails for access and operations.</p></div>
                <div className="card-sm"><strong>3. Activity</strong><p className="small-copy">Review the governance trail for user and admin actions.</p></div>
              </div>
            </div>
            <div className="card">
              <p className="label" style={{ marginBottom: '0.5rem' }}>Admin Quick Actions</p>
              <div className="stack-sm">
                <div className="card-sm">
                  <strong>Open User Controls</strong>
                  <p className="small-copy">Inspect user status and RBAC controls for this session.</p>
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
              currentUserId={currentUserId}
              realtimeTick={realtimeTick}
            />
          ) : (
            <div className="stack-sm">
              <p className="label">Access Restricted</p>
              <p className="body-copy">User and role governance is available to admin users only.</p>
            </div>
          )}
        </div>
      )}

      {section === 'activity' && (
        <div className="stack" style={{ gap: '1rem' }}>
          <div className="card">
            <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.65rem' }}>
              <p className="label">Routing Review</p>
              <span className="badge badge-completed">Admin view</span>
            </div>
            {routerSummaryLoading ? (
              <p className="small-copy">Loading router review summary...</p>
            ) : routerSummaryError ? (
              <div className="card-sm">
                <strong>Routing review unavailable</strong>
                <p className="small-copy" style={{ marginTop: '0.35rem' }}>{routerSummaryError}</p>
              </div>
            ) : routerSummary ? (
              <div className="grid-2" style={{ gap: '0.85rem', alignItems: 'start' }}>
                <div className="stack-sm">
                  <div className="grid-2" style={{ gap: '0.6rem' }}>
                    <InfoTile label="Total Reviews" value={String(routerSummary.total_reviews)} />
                    <InfoTile label="Escalations" value={String(routerSummary.escalated_count)} />
                    <InfoTile label="Low Confidence" value={String(routerSummary.low_confidence_count)} />
                    <InfoTile label="Path Mismatches" value={String(routerSummary.path_mismatch_count)} />
                  </div>
                  <div className="card-sm">
                    <p className="label" style={{ marginBottom: '0.45rem' }}>Top Selected Agents</p>
                    <div className="stack-sm">
                      {routerSummary.top_selected_agents.length > 0 ? routerSummary.top_selected_agents.map((item) => (
                        <div key={item.agent} className="flex-between" style={{ gap: '0.75rem' }}>
                          <span className="small-copy">{formatActionLabel(item.agent)}</span>
                          <span className="source-pill">{item.count}</span>
                        </div>
                      )) : (
                        <p className="small-copy">No router decisions logged yet.</p>
                      )}
                    </div>
                  </div>
                </div>
                <div className="stack-sm">
                  <div className="card-sm">
                    <p className="label" style={{ marginBottom: '0.45rem' }}>Decision Source Breakdown</p>
                    <div className="stack-sm">
                      {Object.entries(routerSummary.decision_source_counts).length > 0 ? Object.entries(routerSummary.decision_source_counts).map(([source, count]) => (
                        <div key={source} className="flex-between" style={{ gap: '0.75rem' }}>
                          <span className="small-copy">{source.replace(/_/g, ' ')}</span>
                          <span className="source-pill">{count}</span>
                        </div>
                      )) : (
                        <p className="small-copy">No routing source data available.</p>
                      )}
                    </div>
                  </div>
                  <div className="card-sm">
                    <p className="label" style={{ marginBottom: '0.45rem' }}>Recent Misroutes</p>
                    <div className="stack-sm">
                      {routerSummary.recent_misroutes.length > 0 ? routerSummary.recent_misroutes.slice(0, 3).map((item) => (
                        <div key={item.audit_log_id} className="card-sm">
                          <strong>{formatActionLabel(item.selected_agent || 'general_agent')}</strong>
                          <p className="small-copy" style={{ marginTop: '0.25rem' }}>{item.query || 'No query text available.'}</p>
                        </div>
                      )) : (
                        <p className="small-copy">No misroutes detected in the current review window.</p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <p className="small-copy">No routing summary available yet.</p>
            )}
          </div>

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
                  <div key={user.user_id} className="card-sm" style={{ minWidth: '180px' }}>
                    <strong style={{ display: 'block' }}>{user.full_name}</strong>
                    <p className="small-copy" style={{ marginTop: '0.2rem' }}>{user.email}</p>
                    <p className="small-copy" style={{ marginTop: '0.2rem' }}>
                      {user.role === 'admin' ? 'Admin' : 'User'} • {user.session_count || 1} session{(user.session_count || 1) === 1 ? '' : 's'}
                    </p>
                    {user.connected_at && (
                      <p className="small-copy" style={{ marginTop: '0.2rem', opacity: 0.8 }}>
                        Connected {formatRelativeTime(user.connected_at)}
                      </p>
                    )}
                  </div>
                )) : (
                  <p className="small-copy">No users are active right now.</p>
                )}
              </div>
            </div>
          )}

          <div className="grid-2" style={{ gap: '1rem', alignItems: 'start' }}>
            <div className="card">
              <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.65rem' }}>
                <p className="label">Activity Trail</p>
                <button type="button" className="tab-btn" onClick={handleExportActivity} disabled={activityEvents.length === 0}>
                  Export
                </button>
              </div>
              {isAdmin && (
                <div className="card-sm" style={{ marginBottom: '0.85rem', borderLeft: '3px solid var(--accent-green)' }}>
                  <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
                    <div>
                      <p className="label" style={{ marginBottom: '0.25rem' }}>Active Now</p>
                      <strong>{activeUsers.length} active user{activeUsers.length === 1 ? '' : 's'}</strong>
                    </div>
                    <span className="badge badge-completed">Live view</span>
                  </div>
                  <div className="flex-row" style={{ flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.75rem' }}>
                    {activeUsers.length > 0 ? activeUsers.map((user) => (
                      <div key={user.user_id} className="source-pill" style={{ display: 'grid', gap: '0.1rem', padding: '0.55rem 0.75rem' }}>
                        <strong style={{ display: 'block' }}>{user.full_name}</strong>
                        <span style={{ fontSize: '0.72rem', opacity: 0.82 }}>{user.role === 'admin' ? 'Admin' : 'User'} • {user.session_count || 1} session{(user.session_count || 1) === 1 ? '' : 's'}</span>
                      </div>
                    )) : (
                      <p className="small-copy">No users are active right now.</p>
                    )}
                  </div>
                </div>
              )}
              <div className="grid-3" style={{ gap: '0.6rem', marginBottom: '0.85rem' }}>
                <input
                  value={activitySearch}
                  onChange={(event) => setActivitySearch(event.target.value)}
                  placeholder="Search activity"
                  className="input"
                />
                {isAdmin ? (
                  <select value={activityUserId} onChange={(event) => setActivityUserId(event.target.value)} className="input">
                    <option value="">View activity for all users</option>
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
                  <option value="router_decision_reviewed">Router Decision Reviewed</option>
                  <option value="router_path_reviewed">Router Path Reviewed</option>
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
                <strong>Who can manage controls?</strong>
                <p className="small-copy">Admins manage users, roles, and governance settings.</p>
              </div>
              <div className="card-sm">
                <strong>How is access applied?</strong>
                <p className="small-copy">Access controls determine which parts of the system each user can use.</p>
              </div>
              <div className="card-sm">
                <strong>What is protected?</strong>
                <p className="small-copy">Admin self-deactivation and invalid governance actions are blocked.</p>
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
