import type { CitationRecord } from '../types/audit';
import { PdfViewer } from './PdfViewer';

interface DocumentViewerModalProps {
  open: boolean;
  citation: CitationRecord | null;
  onClose: () => void;
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
  return 'Source Document';
}

function copyText(value: string | null | undefined) {
  if (!value) {
    return;
  }
  if (navigator.clipboard?.writeText) {
    void navigator.clipboard.writeText(value);
  }
}

function openSource(value: string | null | undefined) {
  if (!value) {
    return;
  }
  window.open(value, '_blank', 'noopener,noreferrer');
}

function renderField(label: string, value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') {
    return null;
  }

  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export function DocumentViewerModal({ open, citation, onClose }: DocumentViewerModalProps) {
  if (!open || !citation) {
    return null;
  }

  const sourceName = citation.document_name || citation.file_name || citation.document_id || 'Unknown document';
  const sourceType = deriveSourceType(citation);
  const sourceOrigin = citation.citation_origin || citation.source_uri || citation.document_id || 'Unknown origin';
  const citationOrigin = citation.citation_origin || citation.source_uri || citation.chunk_id || 'Citation metadata';

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="citation-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="section-label">Evidence Viewer</p>
            <h3 id="citation-modal-title">Citation details</h3>
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close citation details">
            Close
          </button>
        </div>

        <div className="section-grid">
          <section className="section-block">
            <p className="section-label">Document Information</p>
            <dl className="citation-details">
              {renderField('Document ID', citation.document_id)}
              {renderField('Document Name', sourceName)}
              {renderField('Source URI', citation.source_uri)}
              {renderField('Source Type', sourceType)}
            </dl>
          </section>

          <section className="section-block">
            <p className="section-label">Citation Context</p>
            <dl className="citation-details">
              {renderField('Citation Text', citation.citation_text)}
              {renderField('Anchor Text', citation.anchor_text)}
              {renderField('Page Number', citation.page_number)}
              {renderField('Section Title', citation.section_title)}
            </dl>
          </section>
        </div>

        <section className="section-block">
          <p className="section-label">Evidence Metadata</p>
          <dl className="citation-details">
            {renderField('Linked Transaction', citation.linked_transaction)}
            {renderField('Related Vendor', citation.related_vendor_id)}
            {renderField('Document Identifier', citation.document_id || citation.chunk_id)}
            {renderField('Citation Origin', citationOrigin)}
            {renderField('Source Origin', sourceOrigin)}
          </dl>
        </section>

        <section className="section-block">
          <p className="section-label">Source Navigation Actions</p>
          <div className="query-meta">
            <button
              type="button"
              className="modal-close"
              onClick={() => openSource(citation.source_uri)}
              disabled={!citation.source_uri}
            >
              Open Source
            </button>
            <button
              type="button"
              className="modal-close"
              onClick={() => copyText(citation.citation_text)}
              disabled={!citation.citation_text}
            >
              Copy Citation
            </button>
            <button
              type="button"
              className="modal-close"
              onClick={() => copyText(citation.source_uri)}
              disabled={!citation.source_uri}
            >
              Copy Source URI
            </button>
          </div>
        </section>

        <section className="section-block">
          <p className="section-label">Source Verification</p>
          {citation.source_uri && (sourceType === 'PDF' || sourceType === 'Source Document') ? (
            <p className="body-copy">Evidence Source Verified</p>
          ) : (
            <p className="body-copy">Source information is available for review.</p>
          )}
        </section>

        <PdfViewer citation={citation} />
      </div>
    </div>
  );
}
