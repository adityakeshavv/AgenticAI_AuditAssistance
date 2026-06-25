interface PageNavigatorProps {
  currentPage: number;
  totalPages?: number;
  onPrevious: () => void;
  onNext: () => void;
  onGoToPage: (page: number) => void;
}

export function PageNavigator({ currentPage, totalPages, onPrevious, onNext, onGoToPage }: PageNavigatorProps) {
  const canGoPrevious = currentPage > 1;
  const canGoNext = totalPages ? currentPage < totalPages : true;

  return (
    <div className="section-block">
      <p className="section-label">Page Navigation</p>
      <div className="query-meta">
        <button type="button" className="modal-close" onClick={onPrevious} disabled={!canGoPrevious}>
          Previous Page
        </button>
        <button type="button" className="modal-close" onClick={onNext} disabled={!canGoNext}>
          Next Page
        </button>
        <label className="small-copy" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          Go To Page
          <input
            type="number"
            min={1}
            max={totalPages}
            value={currentPage}
            onChange={(event) => onGoToPage(Number(event.target.value))}
            className="audit-search"
            style={{ width: '90px' }}
          />
        </label>
      </div>
      <p className="small-copy">
        Page {currentPage}
        {totalPages ? ` of ${totalPages}` : ''}
      </p>
    </div>
  );
}
