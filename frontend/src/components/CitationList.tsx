import { useMemo, useState } from 'react';
import type { CitationRecord } from '../types/audit';
import { CitationCard } from './CitationCard';

interface Props { citations: CitationRecord[]; onSelect: (c: CitationRecord) => void; }

export function CitationList({ citations, onSelect }: Props) {
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    if (!search.trim()) return citations;
    const q = search.toLowerCase();
    return citations.filter((c) =>
      [c.document_name, c.file_name, c.document_id, c.section_title, c.citation_text]
        .filter(Boolean).join(' ').toLowerCase().includes(q)
    );
  }, [citations, search]);

  if (!citations.length) {
    return <p className="small-copy muted">No citations available.</p>;
  }

  return (
    <div className="stack-sm">
      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
        <input
          type="text"
          className="audit-search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter by document, section, or text…"
          aria-label="Filter citations"
          style={{ flex: 1 }}
        />
        <span className="small-copy" style={{ whiteSpace: 'nowrap' }}>{filtered.length}/{citations.length}</span>
      </div>

      {filtered.length > 0 ? (
        <div className="citation-list">
          {filtered.map((c, i) => (
            <CitationCard
              key={`${c.document_id ?? 'cit'}-${c.chunk_id ?? i}`}
              citation={c}
              onClick={() => onSelect(c)}
            />
          ))}
        </div>
      ) : (
        <p className="small-copy muted">No citations match the filter.</p>
      )}
    </div>
  );
}
