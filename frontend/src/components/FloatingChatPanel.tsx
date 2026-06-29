// FloatingChatPanel is no longer used as the primary navigation pattern —
// the top-nav tabs in App.tsx handle page switching directly.
// Kept for backwards compatibility if re-used elsewhere.

import { AuditQueryPage } from './AuditQueryPage';

interface FloatingChatPanelProps {
  open: boolean;
  onClose: () => void;
}

export function FloatingChatPanel({ open, onClose }: FloatingChatPanelProps) {
  if (!open) return null;

  return (
    <div
      className="side-panel-backdrop"
      role="presentation"
      onClick={onClose}
    >
      <aside
        className="side-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Audit assistant workspace"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="side-panel-header">
          <div>
            <p className="eyebrow" style={{ margin: 0 }}>Audit Assistant</p>
            <h2 style={{ margin: '0.2rem 0 0', fontSize: '1.1rem' }}>Workspace</h2>
          </div>
          <button type="button" className="btn btn-secondary" onClick={onClose}>✕ Close</button>
        </div>
        <div className="side-panel-body">
          <AuditQueryPage />
        </div>
      </aside>
    </div>
  );
}
