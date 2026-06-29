interface InvestigationItem {
  query: string;
  severity: string;
  time: string;
  status: string;
}

const fallbackItems: InvestigationItem[] = [
  { query: 'Investigate vendor VND-02731', severity: 'HIGH', time: '12 min ago', status: 'Completed' },
  { query: 'Show flagged transactions and related documents', severity: 'MEDIUM', time: '34 min ago', status: 'Completed' },
  { query: 'Investigate transaction TXN-C8972378', severity: 'HIGH', time: '1 hr ago', status: 'In Review' },
  { query: 'Which policy was violated by TXN-C8972378?', severity: 'MEDIUM', time: '2 hr ago', status: 'Completed' },
  { query: 'High-risk vendor payment analysis Q2', severity: 'LOW', time: '3 hr ago', status: 'Archived' },
];

interface Props {
  items?: InvestigationItem[];
  onOpenInvestigation?: (query: string) => void;
}

export function RecentInvestigations({ items = fallbackItems, onOpenInvestigation }: Props) {
  return (
    <article className="dashboard-widget">
      <div className="dashboard-widget-header">
        <div>
          <p className="label" style={{ margin: 0 }}>Recent Investigations</p>
          <h3 style={{ margin: '0.25rem 0 0' }}>Recent audit activity</h3>
        </div>
        <span className="badge badge-completed">{items.length} entries</span>
      </div>
      <div className="stack-sm">
        {items.map((item) => (
          <button
            key={item.query}
            type="button"
            className="investigation-item"
            onClick={() => onOpenInvestigation?.(item.query)}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <strong style={{ display: 'block', fontSize: '0.87rem', marginBottom: '0.2rem' }}>{item.query}</strong>
              <p className="small-copy">{item.time}</p>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.3rem', flexShrink: 0 }}>
              <span className={`risk-pill risk-${item.severity.toLowerCase()}`}>{item.severity}</span>
              <span className="small-copy">{item.status}</span>
            </div>
          </button>
        ))}
      </div>
    </article>
  );
}
