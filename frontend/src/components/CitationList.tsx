import { useMemo, useState } from 'react';
import type { CitationRecord } from '../types/audit';
import { CitationCard } from './CitationCard';

interface CitationListProps {
  citations: CitationRecord[];
  onSelect: (citation: CitationRecord) => void;
}

function buildSourceSummary(citations: CitationRecord[]) {
  if (!citations.length) {
    return 'No citations contributed to this finding.';
  }

  const uniqueDocuments = new Set(
    citations.map((citation) => citation.document_name || citation.file_name || citation.document_id || citation.source_uri || 'Unknown source'),
  );
  const supportingEmails = citations.filter((citation) => {
    const value = `${citation.source_type || ''} ${citation.file_name || ''} ${citation.source_uri || ''}`.toLowerCase();
    return value.includes('email') || value.endsWith('.eml');
  }).length;

  const emailText = supportingEmails > 0 ? `${supportingEmails} supporting email${supportingEmails === 1 ? '' : 's'}` : `${uniqueDocuments.size} source${uniqueDocuments.size === 1 ? '' : 's'}`;
  return `${emailText} and ${citations.length} citation${citations.length === 1 ? '' : 's'} contributed to this finding.`;
}

function matchesQuery(citation: CitationRecord, query: string) {
  if (!query.trim()) {
    return true;
  }

  const haystack = [
    citation.document_name,
    citation.file_name,
    citation.document_id,
    citation.section_title,
    citation.citation_text,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  return haystack.includes(query.toLowerCase());
}

export function CitationList({ citations, onSelect }: CitationListProps) {
  const [search, setSearch] = useState('');

  const filteredCitations = useMemo(
    () => citations.filter((citation) => matchesQuery(citation, search)),
    [citations, search],
  );

  if (!citations.length) {
    return <p className="small-copy muted">No citations available.</p>;
  }

  return (
    <div className="citation-list">
      <div className="metric-card">
        <p className="section-label">Source Summary</p>
        <p className="body-copy">{buildSourceSummary(citations)}</p>
      </div>

      <div className="metric-card">
        <p className="section-label">Search Citations</p>
        <input
          type="text"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Filter by document, text, or section"
          aria-label="Filter citations"
          className="audit-search"
        />
        <p className="small-copy">{filteredCitations.length} of {citations.length} citations shown</p>
      </div>

      {filteredCitations.length > 1 ? (
        <div className="metric-card">
          <p className="section-label">Review Order</p>
          <div className="query-meta">
            {filteredCitations.map((citation, index) => (
              <button
                key={`${citation.document_id ?? 'citation'}-nav-${citation.chunk_id ?? index}`}
                type="button"
                className="modal-close"
                onClick={() => {
                  const element = document.getElementById(`citation-review-${index}`);
                  element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }}
              >
                Citation {index + 1}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="citation-list">
        {filteredCitations.length > 0 ? (
          filteredCitations.map((citation, index) => (
            <div key={`${citation.document_id ?? 'citation'}-${citation.chunk_id ?? index}`} id={`citation-review-${index}`}>
              <CitationCard citation={citation} onClick={() => onSelect(citation)} />
              {index < filteredCitations.length - 1 ? <div className="small-copy">↓</div> : null}
            </div>
          ))
        ) : (
          <p className="small-copy muted">No citations match the current filter.</p>
        )}
      </div>
    </div>
  );
}
