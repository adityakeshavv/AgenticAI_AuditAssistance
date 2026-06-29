const fallbackData = [
  { label: 'Transaction Agent', value: 42, color: '#3b82f6' },
  { label: 'Vendor Agent', value: 27, color: '#10b981' },
  { label: 'Compliance Agent', value: 19, color: '#f59e0b' },
  { label: 'Document Retrieval', value: 31, color: '#8b5cf6' },
];

export function AgentActivityChart({ data = fallbackData }: { data?: typeof fallbackData }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <article className="dashboard-widget">
      <div className="dashboard-widget-header">
        <div>
          <p className="label" style={{ margin: 0 }}>Agent Activity</p>
          <h3 style={{ margin: '0.25rem 0 0' }}>Investigations by agent</h3>
        </div>
        <span className="badge badge-running">{total} total</span>
      </div>
      <div className="bar-chart">
        {data.map((item) => (
          <div key={item.label} className="bar-row">
            <div className="bar-label">
              <span>{item.label}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <strong style={{ color: item.color }}>{item.value}</strong>
                <span className="small-copy">({((item.value / total) * 100).toFixed(0)}%)</span>
              </span>
            </div>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${(item.value / max) * 100}%`, background: `linear-gradient(90deg, ${item.color}99, ${item.color})` }} />
            </div>
          </div>
        ))}
      </div>
    </article>
  );
}
