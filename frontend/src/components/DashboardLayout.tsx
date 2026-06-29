import type { ReactNode } from 'react';

interface DashboardLayoutProps {
  title: string;
  subtitle: string;
  actions?: ReactNode;
  children: ReactNode;
}

export function DashboardLayout({ title, subtitle, actions, children }: DashboardLayoutProps) {
  return (
    <div
      className="audit-dashboard-shell"
      style={{
        minHeight: '100vh',
        background:
          'radial-gradient(circle at top left, rgba(37, 99, 235, 0.16), transparent 30%), radial-gradient(circle at top right, rgba(14, 165, 233, 0.12), transparent 26%), #08111f',
        color: '#e2e8f0',
      }}
    >
      <div style={{ maxWidth: '1480px', margin: '0 auto', padding: '1.5rem 1.5rem 2rem' }}>
        <header
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: '1rem',
            padding: '1.25rem 1.35rem',
            borderRadius: '22px',
            background: 'rgba(15, 23, 42, 0.9)',
            border: '1px solid rgba(148, 163, 184, 0.16)',
            boxShadow: '0 20px 60px rgba(15, 23, 42, 0.24)',
            marginBottom: '1.25rem',
          }}
        >
          <div>
            <p className="eyebrow" style={{ margin: 0 }}>
              Audit Operations Center
            </p>
            <h1 style={{ margin: '0.35rem 0 0.35rem', fontSize: '2rem', color: '#f8fafc' }}>{title}</h1>
            <p style={{ margin: 0, color: '#cbd5e1', lineHeight: 1.6, maxWidth: '70ch' }}>{subtitle}</p>
          </div>
          {actions ? <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>{actions}</div> : null}
        </header>
        {children}
      </div>
    </div>
  );
}
