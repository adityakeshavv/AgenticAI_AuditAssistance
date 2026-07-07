import { useEffect, useState } from 'react';
import { AuthPage } from './components/AuthPage';
import { AuditDashboard } from './components/AuditDashboard';
import { DatabaseConnectionsPage } from './components/DatabaseConnectionsPage';
import { AuditQueryPage } from './components/AuditQueryPage';
import { ChatPage } from './components/chat/ChatPage';
import { clearAuthSession, fetchCurrentUser, getStoredAuthToken, saveAuthSession } from './services/authApi';
import type { AuthResponse, AuthUser } from './types/auth';

type Page = 'dashboard' | 'workspace' | 'chat' | 'connections';

export default function App() {
  const [page, setPage] = useState<Page>('dashboard');
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

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
      {/* ── Top Navigation ── */}
      <nav className="topnav">
        <a
          className="topnav-brand"
          href="#"
          onClick={(e) => { e.preventDefault(); setPage('dashboard'); }}
        >
          <div className="topnav-brand-icon">A</div>
          AuditAI
        </a>

        <div className="topnav-tabs">
          <button
            className={`topnav-tab${page === 'dashboard' ? ' active' : ''}`}
            onClick={() => setPage('dashboard')}
          >
            Dashboard
          </button>
          <button
            className={`topnav-tab${page === 'chat' ? ' active' : ''}`}
            onClick={() => setPage('chat')}
          >
            Copilot Chat
          </button>
          <button
            className={`topnav-tab${page === 'workspace' ? ' active' : ''}`}
            onClick={() => setPage('workspace')}
          >
            Audit Workspace
          </button>
          <button
            className={`topnav-tab${page === 'connections' ? ' active' : ''}`}
            onClick={() => setPage('connections')}
          >
            Connections
          </button>
        </div>

        <div className="topnav-actions">
          <div className="status-dot" title="System operational" />
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Operational</span>
          <div style={{ display: 'grid', gap: '0.1rem', textAlign: 'right' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-primary)', fontWeight: 600 }}>
              {authUser.full_name}
            </span>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{authUser.email}</span>
          </div>
          <button className="btn btn-ghost" type="button" onClick={handleLogout}>
            Sign Out
          </button>
        </div>
      </nav>

      {/* ── Page Content ── */}
      {page === 'chat' ? (
        /* Chat takes full height with its own layout */
        <ChatPage />
      ) : page === 'connections' ? (
        <div className="page-content" style={{ overflow: 'auto' }}>
          <DatabaseConnectionsPage />
        </div>
      ) : (
        <div className="page-content" style={{ overflow: 'auto' }}>
          {page === 'dashboard' ? (
            <AuditDashboard onNavigateToWorkspace={() => setPage('chat')} />
          ) : (
            <AuditQueryPage />
          )}
        </div>
      )}
    </div>
  );
}
