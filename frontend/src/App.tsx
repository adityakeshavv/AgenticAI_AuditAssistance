import { useState } from 'react';
import { AuditDashboard } from './components/AuditDashboard';
import { AuditQueryPage } from './components/AuditQueryPage';
import { ChatPage } from './components/chat/ChatPage';

type Page = 'dashboard' | 'workspace' | 'chat';

export default function App() {
  const [page, setPage] = useState<Page>('dashboard');

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
        </div>

        <div className="topnav-actions">
          <div className="status-dot" title="System operational" />
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Operational</span>
        </div>
      </nav>

      {/* ── Page Content ── */}
      {page === 'chat' ? (
        /* Chat takes full height with its own layout */
        <ChatPage />
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
