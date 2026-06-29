import type { CitationRecord } from '../types/audit';

interface CitationCardProps { citation: CitationRecord; onClick: () => void; }

function deriveSourceType(c: CitationRecord) {
  const cand = (c.source_type || c.file_name || c.source_uri || '').toLowerCase();
  if (cand.endsWith('.eml') || cand.includes('email')) return 'Email';
  if (cand.endsWith('.pdf')) return 'PDF';
  if (cand.endsWith('.docx') || cand.endsWith('.doc')) return 'Word';
  if (cand.endsWith('.txt')) return 'Text';
  return 'Document';
}

const TYPE_ICON: Record<string, string> = {
  Email: '✉', PDF: '📄', Word: '📝', Text: '📃', Document: '📋',
};

export function CitationCard({ citation, onClick }: CitationCardProps) {
  const sourceName = citation.document_name || citation.file_name || citation.document_id || 'Unknown document';
  const sourceType = deriveSourceType(citation);
  const metaBits = [
    citation.page_number != null ? `Page ${citation.page_number}` : null,
    citation.section_title || null,
    citation.linked_transaction ? `Tx: ${citation.linked_transaction}` : null,
  ].filter((v): v is string => Boolean(v));

  return (
    <button type="button" className="citation-card" onClick={onClick}>
      <div className="citation-card-top">
        <strong style={{ fontSize: '0.88rem' }}>
          <span style={{ marginRight: '0.4rem' }}>{TYPE_ICON[sourceType] ?? '📋'}</span>
          {sourceName}
        </strong>
        {citation.relevance_score != null && (
          <span className="citation-score">
            {(citation.relevance_score * 100).toFixed(0)}% confidence
          </span>
        )}
      </div>
      <div className="citation-meta">
        <span>{sourceType}</span>
        {metaBits.map((m) => <span key={m}>{m}</span>)}
      </div>
      {citation.citation_text && (
        <p className="citation-text">{citation.citation_text}</p>
      )}
    </button>
  );
}
