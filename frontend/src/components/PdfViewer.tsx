import type { CitationRecord } from '../types/audit';

interface Props { citation: CitationRecord | null; }

export function PdfViewer({ citation }: Props) {
  if (!citation?.source_uri) return null;
  const isPdf = citation.source_uri.toLowerCase().endsWith('.pdf');
  if (!isPdf) return null;

  return (
    <div>
      <p className="label" style={{ marginBottom: '0.5rem' }}>Document Preview</p>
      <iframe
        src={citation.source_uri}
        title="Document preview"
        style={{ width: '100%', height: 420, border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: '#fff' }}
      />
    </div>
  );
}
