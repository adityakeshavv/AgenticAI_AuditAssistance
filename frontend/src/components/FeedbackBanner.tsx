type FeedbackVariant = 'error' | 'success' | 'info' | 'warning';

interface FeedbackBannerProps {
  title: string;
  message: string;
  variant?: FeedbackVariant;
}

const VARIANT_STYLES: Record<FeedbackVariant, { border: string; title: string; background: string }> = {
  error: {
    border: 'rgba(248, 113, 113, 0.35)',
    title: '#fca5a5',
    background: 'rgba(248, 113, 113, 0.08)',
  },
  success: {
    border: 'rgba(74, 222, 128, 0.35)',
    title: '#86efac',
    background: 'rgba(74, 222, 128, 0.08)',
  },
  info: {
    border: 'rgba(96, 165, 250, 0.35)',
    title: '#93c5fd',
    background: 'rgba(96, 165, 250, 0.08)',
  },
  warning: {
    border: 'rgba(251, 191, 36, 0.35)',
    title: '#fcd34d',
    background: 'rgba(251, 191, 36, 0.08)',
  },
};

export function FeedbackBanner({ title, message, variant = 'info' }: FeedbackBannerProps) {
  const styles = VARIANT_STYLES[variant];

  return (
    <div
      className="card-sm"
      style={{
        borderLeft: `3px solid ${styles.border}`,
        background: styles.background,
      }}
    >
      <p className="label" style={{ color: styles.title, marginBottom: '0.25rem' }}>
        {title}
      </p>
      <p className="body-copy" style={{ margin: 0 }}>
        {message}
      </p>
    </div>
  );
}
