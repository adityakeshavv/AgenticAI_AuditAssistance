import type { CitationRecord } from '../types/audit';

interface CitationCardProps {
  citation: CitationRecord;
  onClick: () => void;
}

function deriveSourceType(citation: CitationRecord) {
  const candidate = (citation.source_type || citation.file_name || citation.source_uri || '').toLowerCase();
  if (candidate.endsWith('.eml') || candidate.includes('email')) {
    return 'Email';
  }
  if (candidate.endsWith('.pdf')) {
    return 'PDF';
  }
  if (candidate.endsWith('.docx') || candidate.endsWith('.doc')) {
    return 'Word Document';
  }
  if (candidate.endsWith('.txt')) {
    return 'Text File';
  }
  if (candidate) {
    return 'Source Document';
  }
  return 'Source Document';
}

export function CitationCard({ citation, onClick }: CitationCardProps) {
  const sourceName = citation.document_name || citation.file_name || citation.document_id || 'Unknown document';
  const sourceType = deriveSourceType(citation);
  const metaBits = [
    citation.page_number != null ? `Page ${citation.page_number}` : null,
    citation.section_title || null,
  ].filter((value): value is string => Boolean(value));
  const confidenceLabel =
    citation.relevance_score != null ? `Evidence confidence ${citation.relevance_score.toFixed(2)}` : 'Evidence confidence not provided';

  return (
    <button type="button" className="citation-card" onClick={onClick}>
      <div className="citation-card-top">
        <strong>{sourceName}</strong>
        <span className="citation-score">{confidenceLabel}</span>
      </div>
      <div className="citation-meta">
        <span>{sourceType}</span>
        {metaBits.map((meta) => (
          <span key={meta}>{meta}</span>
        ))}
      </div>
      <p className="citation-text">{citation.citation_text || 'No citation text available.'}</p>
    </button>
  );
}
