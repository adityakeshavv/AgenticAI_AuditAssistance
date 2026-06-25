interface SourceTraceCardProps {
  source: string;
}

export function SourceTraceCard({ source }: SourceTraceCardProps) {
  return (
    <article className="supporting-document-item">
      <p className="supporting-document-title">{source}</p>
      <p className="supporting-document-detail">Source involved in the audit response.</p>
    </article>
  );
}
