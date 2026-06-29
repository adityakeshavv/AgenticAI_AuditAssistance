const fallbackStats = [
  { label: 'Agents Available', value: '5', note: 'Transaction, Vendor, Compliance, Approval, Document Retrieval', color: 'var(--accent-blue)' },
  { label: 'Documents Indexed', value: '835', note: 'Metadata-backed enterprise documents ready for review', color: 'var(--accent-cyan)' },
  { label: 'Structured Records', value: '128K+', note: 'Transactions and audit entities in PostgreSQL', color: 'var(--accent-violet)' },
  { label: 'Evidence Linked', value: '2,918', note: 'Structured and document evidence stitched into audit responses', color: 'var(--accent-green)' },
  { label: 'System Status', value: 'Operational', note: 'Backend, retrieval, and response composition are active', color: 'var(--accent-green)' },
];

export function SystemOverview({ stats = fallbackStats }: { stats?: typeof fallbackStats }) {
  return (
    <article className="dashboard-widget">
      <div className="dashboard-widget-header">
        <div>
          <p className="label" style={{ margin: 0 }}>System Overview</p>
          <h3 style={{ margin: '0.25rem 0 0' }}>Platform health and coverage</h3>
        </div>
        <div className="status-dot" title="System operational" />
      </div>
      <div className="stack-sm">
        {stats.map((stat) => (
          <div
            key={stat.label}
            style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem',
              background: 'var(--bg-panel)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)', padding: '0.75rem 1rem',
              borderLeft: `3px solid ${stat.color}`,
            }}
          >
            <div>
              <p className="small-copy" style={{ marginBottom: '0.1rem' }}>{stat.label}</p>
              <p className="body-copy" style={{ fontSize: '0.78rem' }}>{stat.note}</p>
            </div>
            <strong style={{ color: stat.color, fontWeight: 700, fontSize: '1rem', whiteSpace: 'nowrap' }}>{stat.value}</strong>
          </div>
        ))}
      </div>
    </article>
  );
}
