interface EvidenceFlowProps {
  structuredCount: number;
  documentCount: number;
  citationCount: number;
  findingLabel: string;
}

export function EvidenceFlow({ structuredCount, documentCount, citationCount, findingLabel }: EvidenceFlowProps) {
  const stages = [
    { label: 'Transaction Records', count: structuredCount },
    { label: 'Supporting Documents', count: documentCount },
    { label: 'Citations', count: citationCount },
    { label: 'Audit Finding', count: findingLabel },
  ];

  return (
    <article className="dashboard-widget">
      <div className="dashboard-widget-header">
        <div>
          <p className="section-label" style={{ margin: 0 }}>
            Evidence Flow
          </p>
          <h3 style={{ margin: '0.35rem 0 0' }}>How evidence moved through the workflow</h3>
        </div>
      </div>

      <div style={{ display: 'grid', gap: '0.75rem' }}>
        {stages.map((stage, index) => (
          <div key={stage.label} style={{ display: 'grid', gap: '0.4rem' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                gap: '1rem',
                alignItems: 'center',
              }}
            >
              <strong>{stage.label}</strong>
              <span className="risk-pill risk-low" style={{ margin: 0 }}>
                {stage.count}
              </span>
            </div>
            {index < stages.length - 1 ? (
              <div style={{ display: 'grid', justifyItems: 'center' }}>
                <div style={{ width: '2px', height: '18px', background: 'rgba(148, 163, 184, 0.38)' }} />
                <div style={{ color: '#94a3b8' }}>↓</div>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </article>
  );
}
