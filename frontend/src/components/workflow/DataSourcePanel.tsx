interface DataSourcePanelProps {
  sources: string[];
  structuredCount: number;
  documentCount: number;
}

function detectSourceType(source: string) {
  const lower = source.toLowerCase();
  if (lower.includes('transaction')) return 'Structured Table';
  if (lower.includes('vendor')) return 'Structured Table';
  if (lower.includes('compliance')) return 'Structured Table';
  if (lower.includes('document')) return 'Document Metadata';
  if (lower.endsWith('.pdf')) return 'PDF';
  if (lower.endsWith('.eml') || lower.includes('email')) return 'Email';
  if (lower.includes('policy')) return 'Policy';
  return 'Source';
}

function displayCount(source: string, structuredCount: number, documentCount: number) {
  const lower = source.toLowerCase();
  if (lower.includes('transaction') || lower.includes('vendor') || lower.includes('compliance')) {
    return `${structuredCount} records retrieved`;
  }
  if (lower.includes('document') || lower.endsWith('.pdf') || lower.endsWith('.eml') || lower.includes('policy')) {
    return `${documentCount} documents retrieved`;
  }
  return 'Referenced in workflow';
}

export function DataSourcePanel({ sources, structuredCount, documentCount }: DataSourcePanelProps) {
  return (
    <article className="dashboard-widget">
      <div className="dashboard-widget-header">
        <div>
          <p className="section-label" style={{ margin: 0 }}>
            Data Sources
          </p>
          <h3 style={{ margin: '0.35rem 0 0' }}>Sources accessed during execution</h3>
        </div>
      </div>

      <div style={{ display: 'grid', gap: '0.75rem' }}>
        {sources.length > 0 ? (
          sources.map((source) => (
            <div
              key={source}
              style={{
                borderRadius: '16px',
                padding: '0.85rem 1rem',
                background: 'rgba(15, 23, 42, 0.72)',
                border: '1px solid rgba(148, 163, 184, 0.14)',
                display: 'grid',
                gap: '0.25rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                <strong>{source}</strong>
                <span className="small-copy">{detectSourceType(source)}</span>
              </div>
              <p className="body-copy" style={{ margin: 0 }}>
                {displayCount(source, structuredCount, documentCount)}
              </p>
            </div>
          ))
        ) : (
          <p className="body-copy" style={{ margin: 0 }}>
            No explicit source list was returned, so source labels are derived from the current audit response.
          </p>
        )}
      </div>
    </article>
  );
}
