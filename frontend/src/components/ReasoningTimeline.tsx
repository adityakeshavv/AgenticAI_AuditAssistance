interface ReasoningTimelineProps {
  steps: string[];
}

export function ReasoningTimeline({ steps }: ReasoningTimelineProps) {
  if (steps.length === 0) {
    return <p className="body-copy">No reasoning steps were returned.</p>;
  }

  return (
    <ol className="list-block">
      {steps.map((step, index) => (
        <li key={`${step}-${index}`}>
          <strong>{index + 1}.</strong> {step}
        </li>
      ))}
    </ol>
  );
}
