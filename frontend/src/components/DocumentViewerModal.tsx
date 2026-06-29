import type { CitationRecord } from '../types/audit';
import { PdfViewer } from './PdfViewer';

interface Props { open: boolean; citation: CitationRecord | null; onClose: () => void; }

function deriveSourceType(c: CitationRecord) {
  const cand = (c.source_type || c.file_name || c.source_uri || '').toLowerCase();
  if (cand.endsWith('.eml') || cand.includes('email')) return 'Email';
  if (cand.endsWith('.pdf')) return 'PDF';
  if (cand.endsWith('.docx')) return 'Word Document';
  return 'Source Document';
}

function Field({ label, value }: { label: string; value?: string | number | null }) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export function DocumentViewerModal({ open, citation, onClose }: Props) {
  if (!open || !citation) return null;

  const sourceName = citation.document_name || citation.file_name || citation.document_id || 'Unknown document';
  const sourceType = deriveSourceType(citation);

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="citation-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow" style={{ marginBottom: '0.3rem' }}>Evidence Viewer</p>
            <h3 id="citation-modal-title" style={{ fontSize: '1rem' }}>{sourceName}</h3>
          </div>
          <button className="btn btn-secondary" onClick={onClose} aria-label="Close">
            ✕ Close
          </button>
        </div>

        <div className="modal-body">
          {/* Document Info + Citation Context side-by-side */}
          <div className="grid-2" style={{ gap: '1rem' }}>
            <div>
              <p className="label" style={{ marginBottom: '0.5rem' }}>Document Information</p>
              <dl className="citation-details">
                <Field label="Document ID" value={citation.document_id} />
                <Field label="Name" value={sourceName} />
                <Field label="Type" value={sourceType} />
                <Field label="Source URI" value={citation.source_uri} />
              </dl>
            </div>
            <div>
              <p className="label" style={{ marginBottom: '0.5rem' }}>Citation Context</p>
              <dl className="citation-details">
                <Field label="Citation Text" value={citation.citation_text} />
                <Field label="Anchor Text" value={citation.anchor_text} />
                <Field label="Page Number" value={citation.page_number} />
                <Field label="Section" value={citation.section_title} />
              </dl>
            </div>
          </div>

          {/* Evidence Metadata */}
          <div>
            <p className="label" style={{ marginBottom: '0.5rem' }}>Evidence Metadata</p>
            <dl className="citation-details">
              <Field label="Linked Transaction" value={citation.linked_transaction} />
              <Field label="Related Vendor" value={citation.related_vendor_id} />
              <Field label="Chunk ID" value={citation.chunk_id} />
              <Field label="Relevance Score" value={citation.relevance_score != null ? `${(citation.relevance_score * 100).toFixed(1)}%` : null} />
            </dl>
          </div>

          {/* Actions */}
          <div>
            <p className="label" style={{ marginBottom: '0.5rem' }}>Actions</p>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button
                className="btn btn-primary"
                onClick={() => citation.source_uri && window.open(citation.source_uri, '_blank', 'noopener,noreferrer')}
                disabled={!citation.source_uri}
              >
                Open Source ↗
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => citation.citation_text && navigator.clipboard?.writeText(citation.citation_text)}
                disabled={!citation.citation_text}
              >
                Copy Citation Text
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => citation.source_uri && navigator.clipboard?.writeText(citation.source_uri)}
                disabled={!citation.source_uri}
              >
                Copy URI
              </button>
            </div>
          </div>

          <PdfViewer citation={citation} />
        </div>
      </div>
    </div>
  );
}
