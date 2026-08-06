import { useEffect, useMemo, useState } from 'react';
import { AuthPage } from './components/AuthPage';
import { AuditDashboard } from './components/AuditDashboard';
import { AuditQueryPage } from './components/AuditQueryPage';
import { KnowledgeGraphPage } from './components/KnowledgeGraphPage';
import { GovernancePage } from './components/GovernancePage';
import { WorkspaceManagementPage } from './components/WorkspaceManagementPage';
import { DatabaseConnectionsPage } from './components/DatabaseConnectionsPage';
import { ChatPage } from './components/chat/ChatPage';
import { clearAuthSession, fetchCurrentUser, getStoredAuthToken, saveAuthSession } from './services/authApi';
import { getSelectedDatabaseConnectionId, setSelectedDatabaseConnectionId } from './services/databaseConnectionsApi';
import { getSelectedWorkspaceId, listWorkspaces, setSelectedWorkspaceId } from './services/workspacesApi';
import { connectRealtimeSocket } from './services/realtimeSocket';
import type { AuthResponse, AuthUser } from './types/auth';
import type { WorkspaceRecord } from './types/workspace';

type Page = 'dashboard' | 'workspaces' | 'sources' | 'audit' | 'graph' | 'chat' | 'governance';

const JOURNEY_STEPS: Array<{ key: Page; label: string; detail: string }> = [
  { key: 'workspaces', label: '1. Workspace', detail: 'Create or select the audit workspace.' },
  { key: 'sources', label: '2. Data Source', detail: 'Connect databases and document sources.' },
  { key: 'audit', label: '3. Audit Workspace', detail: 'Run investigations and review evidence.' },
  { key: 'graph', label: '4. Knowledge Graph', detail: 'Explore how entities relate across the audit data.' },
  { key: 'chat', label: '5. Copilot Chat', detail: 'Continue with follow-up questions.' },
];

export default function App() {
  const [page, setPage] = useState<Page>('dashboard');
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [workspaces, setWorkspaces] = useState<WorkspaceRecord[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceIdState] = useState<string | null>(getSelectedWorkspaceId());
  const [realtimeTick, setRealtimeTick] = useState(0);
  const [isRailHovered, setIsRailHovered] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const callbackToken = params.get('token');
    const callbackUser = params.get('user_id');
    const callbackEmail = params.get('email');
    const callbackName = params.get('full_name') || params.get('name');

    if (callbackToken) {
      saveAuthSession(callbackToken, {
        user_id: callbackUser || 'google-user',
        full_name: callbackName || callbackEmail || 'Google User',
        email: callbackEmail || 'user@example.com',
        auth_provider: 'GOOGLE',
        role: 'user',
        is_active: true,
        last_login_at: null,
      });

      const url = new URL(window.location.href);
      url.searchParams.delete('auth');
      url.searchParams.delete('token');
      url.searchParams.delete('user_id');
      url.searchParams.delete('email');
      url.searchParams.delete('full_name');
      url.searchParams.delete('name');
      window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
    }

    const token = getStoredAuthToken();
    if (!token) {
      setAuthLoading(false);
      return;
    }

    fetchCurrentUser(token)
      .then((user) => {
        saveAuthSession(token, user);
        setAuthUser(user);
      })
      .catch(() => {
        clearAuthSession();
        setAuthUser(null);
      })
      .finally(() => setAuthLoading(false));
  }, []);

  useEffect(() => {
    if (!authUser) return;
    let cancelled = false;
    listWorkspaces()
      .then((items) => {
        if (cancelled) return;
        setWorkspaces(items);
        const current = getSelectedWorkspaceId();
        const workspace = items.find((item) => item.workspace_id === current) || items.find((item) => item.is_default) || items[0] || null;
        if (workspace) {
          setActiveWorkspaceIdState(workspace.workspace_id);
          setSelectedWorkspaceId(workspace.workspace_id);
          const activeSource = workspace.active_connection_id || workspace.selected_connection_ids[0] || null;
          setSelectedDatabaseConnectionId(activeSource);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setWorkspaces([]);
      });
    return () => {
      cancelled = true;
    };
  }, [authUser, realtimeTick]);

  useEffect(() => {
    if (!authUser) {
      return;
    }
    let active = true;
    let retryHandle: number | null = null;
    let socket: WebSocket | null = null;

    const connect = () => {
      socket = connectRealtimeSocket(
        (event) => {
          if (!active || event.type === 'realtime_connected') {
            return;
          }
          setRealtimeTick((value) => value + 1);
        },
        (connected) => {
          if (!connected && active) {
            if (retryHandle) {
              window.clearTimeout(retryHandle);
            }
            retryHandle = window.setTimeout(connect, 3000);
          }
        },
      );
    };

    connect();

    return () => {
      active = false;
      if (retryHandle) {
        window.clearTimeout(retryHandle);
      }
      socket?.close();
    };
  }, [authUser]);

  const handleAuthenticated = (session: AuthResponse) => {
    setAuthUser(session.user);
    setAuthLoading(false);
    setPage('dashboard');
  };

  const handleLogout = () => {
    clearAuthSession();
    setAuthUser(null);
    setPage('dashboard');
  };

  const activeWorkspace = useMemo(
    () => workspaces.find((item) => item.workspace_id === activeWorkspaceId) || null,
    [activeWorkspaceId, workspaces],
  );
  const isAdmin = authUser?.role === 'admin';
  const isDashboard = page === 'dashboard';
  const isRailOpen = isDashboard || isRailHovered;

  useEffect(() => {
    if (!isDashboard) {
      setIsRailHovered(false);
    }
  }, [isDashboard]);

  const handleWorkspaceChange = (workspaceId: string) => {
    const workspace = workspaces.find((item) => item.workspace_id === workspaceId) || null;
    setActiveWorkspaceIdState(workspaceId || null);
    setSelectedWorkspaceId(workspaceId || null);
    if (workspace) {
      const activeSource = workspace.active_connection_id || workspace.selected_connection_ids[0] || null;
      setSelectedDatabaseConnectionId(activeSource);
    } else {
      setSelectedDatabaseConnectionId(null);
    }
  };

  if (authLoading) {
    return (
      <div className="app-root" style={{ placeItems: 'center' }}>
        <div className="card" style={{ textAlign: 'center', padding: '2rem 2.5rem' }}>
          <p className="eyebrow" style={{ marginBottom: '0.6rem' }}>Audit Copilot</p>
          <h1 style={{ fontSize: '1.5rem', marginBottom: '0.6rem' }}>Loading secure workspace…</h1>
          <p className="body-copy">Verifying your session and preparing the audit environment.</p>
        </div>
      </div>
    );
  }

  if (!authUser) {
    return <AuthPage onAuthenticated={handleAuthenticated} />;
  }

  return (
    <div className="app-root">
      <div className="app-shell">
        <div
          className={`rail-overlay${isRailOpen ? ' open' : ' collapsed'}${isDashboard ? ' dashboard' : ''}`}
          onMouseEnter={() => setIsRailHovered(true)}
          onMouseLeave={() => {
            if (!isDashboard) {
              setIsRailHovered(false);
            }
          }}
        >
          <button
            type="button"
            className="rail-handle"
            aria-label="Show navigation"
            onMouseEnter={() => setIsRailHovered(true)}
            onFocus={() => setIsRailHovered(true)}
          >
            <span />
          </button>

          <aside className="side-rail">
            <a
              className="topnav-brand"
              href="#"
              onClick={(e) => {
                e.preventDefault();
                setPage('dashboard');
              }}
            >
              <div className="topnav-brand-icon">A</div>
              AuditAI
            </a>

            <div className="side-rail-body">
              <div className="rail-section">
                <span className="rail-label">Navigation</span>
                <div className="rail-nav">
                  <button className={`rail-tab${page === 'dashboard' ? ' active' : ''}`} onClick={() => setPage('dashboard')}>
                    Dashboard
                  </button>
                  <button className={`rail-tab${page === 'workspaces' ? ' active' : ''}`} onClick={() => setPage('workspaces')}>
                    Workspaces
                  </button>
                  <button className={`rail-tab${page === 'sources' ? ' active' : ''}`} onClick={() => setPage('sources')}>
                    Data Sources
                  </button>
                  <button className={`rail-tab${page === 'audit' ? ' active' : ''}`} onClick={() => setPage('audit')}>
                    Audit Workspace
                  </button>
                  <button className={`rail-tab${page === 'graph' ? ' active' : ''}`} onClick={() => setPage('graph')}>
                    Knowledge Graph
                  </button>
                  <button className={`rail-tab${page === 'chat' ? ' active' : ''}`} onClick={() => setPage('chat')}>
                    Copilot Chat
                  </button>
                  <button className={`rail-tab${page === 'governance' ? ' active' : ''}`} onClick={() => setPage('governance')}>
                    Governance
                  </button>
                </div>
              </div>

              <div className="rail-section">
                <span className="rail-label">Workflow</span>
                <div style={{ display: 'grid', gap: '0.5rem' }}>
                  {JOURNEY_STEPS.map((step) => {
                    const active = page === step.key;
                    const complete =
                      (step.key === 'workspaces' && !!activeWorkspaceId) ||
                      (step.key === 'sources' && !!(activeWorkspace?.active_connection_id || activeWorkspace?.selected_connection_ids?.length)) ||
                      (step.key === 'audit' && !!authUser);
                    return (
                      <button
                        key={step.key}
                        type="button"
                        className="card-sm"
                        onClick={() => setPage(step.key)}
                        style={{
                          textAlign: 'left',
                          padding: '0.75rem',
                          border: `1px solid ${active ? 'var(--accent-blue)' : 'var(--border)'}`,
                          background: active ? 'rgba(59,130,246,0.08)' : 'var(--bg-panel)',
                        }}
                      >
                        <div className="flex-between" style={{ gap: '0.75rem', alignItems: 'flex-start' }}>
                          <div style={{ minWidth: 0 }}>
                            <strong style={{ display: 'block', fontSize: '0.86rem' }}>{step.label}</strong>
                            <span className="small-copy" style={{ display: 'block', marginTop: '0.15rem' }}>{step.detail}</span>
                          </div>
                          <span className={`source-pill`} style={{ flexShrink: 0 }}>
                            {complete ? 'Ready' : 'Pending'}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="rail-section">
                <span className="rail-label">Workspace</span>
                <select className="input" value={activeWorkspaceId || ''} onChange={(e) => handleWorkspaceChange(e.target.value)}>
                  <option value="">No workspace selected</option>
                  {workspaces.map((workspace) => (
                    <option key={workspace.workspace_id} value={workspace.workspace_id}>
                      {workspace.workspace_name}
                    </option>
                  ))}
                </select>
                <span className="small-copy" style={{ marginTop: '0.35rem' }}>
                  {activeWorkspace
                    ? `Source: ${activeWorkspace.active_connection_id || activeWorkspace.selected_connection_ids[0] || 'not set'}`
                    : 'Select a workspace to scope queries'}
                </span>
              </div>
            </div>

            <div className="rail-footer">
              <div className="status-dot" title="System operational" />
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Operational</span>
              <div style={{ display: 'grid', gap: '0.1rem' }}>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                  {authUser.full_name}
                </span>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{authUser.email}</span>
                <span className="source-pill" style={{ width: 'fit-content', marginTop: '0.25rem' }}>
                  {isAdmin ? 'Admin' : 'User'}
                </span>
              </div>
              <button className="btn btn-ghost" type="button" onClick={handleLogout}>
                Sign Out
              </button>
            </div>
          </aside>
        </div>

        <main className="app-main" style={{ marginLeft: isDashboard ? 280 : 0 }}>
          <div className="page-content" style={{ overflow: 'auto', maxWidth: isDashboard ? 1600 : 'none' }}>
            {page === 'chat' ? (
              <ChatPage
                onNavigateToSources={() => setPage('sources')}
                onNavigateToWorkspaces={() => setPage('workspaces')}
              />
            ) : page === 'sources' ? (
              <DatabaseConnectionsPage isAdminView={isAdmin} realtimeTick={realtimeTick} />
            ) : page === 'workspaces' ? (
              <WorkspaceManagementPage realtimeTick={realtimeTick} />
            ) : page === 'audit' ? (
              <AuditQueryPage />
            ) : page === 'graph' ? (
              <KnowledgeGraphPage />
            ) : page === 'governance' ? (
              <GovernancePage isAdmin={isAdmin} currentUserId={authUser.user_id} realtimeTick={realtimeTick} />
            ) : page === 'dashboard' ? (
              <AuditDashboard
                onNavigateToWorkspace={() => setPage('workspaces')}
                onNavigateToSources={() => setPage('sources')}
                onNavigateToAudit={() => setPage('audit')}
                onNavigateToGraph={() => setPage('graph')}
                onNavigateToChat={() => setPage('chat')}
                activeWorkspaceName={activeWorkspace?.workspace_name || null}
                hasSelectedSource={Boolean(activeWorkspace?.active_connection_id || activeWorkspace?.selected_connection_ids?.length)}
                workspaceCount={workspaces.length}
              />
            ) : (
              <AuditQueryPage />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
