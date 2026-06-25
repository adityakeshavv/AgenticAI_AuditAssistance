import { useEffect, useMemo, useState } from 'react';
import type { CitationRecord } from '../types/audit';
import { PageNavigator } from './PageNavigator';

interface PdfViewerProps {
  citation: CitationRecord;
}

function isPdfSource(citation: CitationRecord) {
  const candidate = `${citation.source_uri || ''} ${citation.file_name || ''} ${citation.document_name || ''}`.toLowerCase();
  return candidate.includes('.pdf') || candidate.includes('pdf');
}

function normalizePageNumber(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? Math.floor(value) : 1;
}

function resolvePdfSource(sourceUri: string) {
  const trimmed = sourceUri.trim();
  if (!trimmed) {
    return '';
  }

  const hashIndex = trimmed.indexOf('#');
  return hashIndex >= 0 ? trimmed.slice(0, hashIndex) : trimmed;
}

export function PdfViewer({ citation }: PdfViewerProps) {
  const [pageNumber, setPageNumber] = useState<number>(normalizePageNumber(citation.page_number));
  const [currentSource, setCurrentSource] = useState<string>(resolvePdfSource(citation.source_uri || ''));

  useEffect(() => {
    setPageNumber(normalizePageNumber(citation.page_number));
    setCurrentSource(resolvePdfSource(citation.source_uri || ''));
  }, [citation]);

  const pdfUrl = useMemo(() => {
    if (!currentSource) {
      return '';
    }
    return `${currentSource}#page=${pageNumber}`;
  }, [currentSource, pageNumber]);

  if (!isPdfSource(citation) || !pdfUrl) {
    return (
      <div className="section-block">
        <p className="section-label">Source Preview</p>
        <p className="body-copy">This source is not a PDF document. Open the source directly to review the evidence.</p>
      </div>
    );
  }

  return (
    <div className="section-block">
      <p className="section-label">PDF Preview</p>
      <PageNavigator
        currentPage={pageNumber}
        totalPages={undefined}
        onPrevious={() => setPageNumber((value) => Math.max(1, value - 1))}
        onNext={() => setPageNumber((value) => value + 1)}
        onGoToPage={(nextPage) => {
          if (!Number.isNaN(nextPage)) {
            setPageNumber(Math.max(1, nextPage));
          }
        }}
      />
      <div className="metric-card" style={{ minHeight: '320px' }}>
        <iframe
          key={pdfUrl}
          src={pdfUrl}
          title={`PDF preview for ${citation.document_name || citation.file_name || citation.document_id || 'document'}`}
          style={{ width: '100%', height: '70vh', border: 0, borderRadius: '8px' }}
        />
      </div>
      <p className="small-copy">
        The browser PDF viewer is showing page {pageNumber}. If the source file is accessible, the document should open at the cited page.
      </p>
    </div>
  );
}
