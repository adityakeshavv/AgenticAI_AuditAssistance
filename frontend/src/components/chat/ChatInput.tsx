import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react';

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  placeholder?: string;
  attachedCount?: number;
  onAttachDocuments?: () => void;
  onOpenSources?: () => void;
  onOpenWorkspaces?: () => void;
}

export function ChatInput({
  value,
  onChange,
  onSubmit,
  disabled,
  placeholder,
  attachedCount,
  onAttachDocuments,
  onOpenSources,
  onOpenWorkspaces,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    if (menuOpen) {
      document.addEventListener('pointerdown', handlePointerDown);
    }

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
    };
  }, [menuOpen]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !disabled) onSubmit();
    }
  };

  const handleInput = (e: ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value);
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
    }
  };

  return (
    <div ref={menuRef} style={{ position: 'relative' }}>
      {menuOpen && (
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 'calc(100% + 0.75rem)',
            background: 'rgba(17,24,39,0.97)',
            border: '1px solid rgba(148,163,184,0.18)',
            borderRadius: '20px',
            boxShadow: '0 28px 60px rgba(15,23,42,0.26)',
            padding: '0.55rem',
            zIndex: 20,
            backdropFilter: 'blur(18px)',
          }}
        >
          <MenuAction
            title="Attach documents"
            description="Upload PDFs, DOCX, emails, or text files from your device."
            onClick={() => {
              setMenuOpen(false);
              onAttachDocuments?.();
            }}
          />
          <MenuAction
            title="Connect sources"
            description="Choose or manage database and document sources."
            onClick={() => {
              setMenuOpen(false);
              onOpenSources?.();
            }}
          />
          <MenuAction
            title="Open workspace"
            description="Jump to the workspace setup and selection flow."
            onClick={() => {
              setMenuOpen(false);
              onOpenWorkspaces?.();
            }}
          />
        </div>
      )}

      {attachedCount ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem', flexWrap: 'wrap' }}>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.35rem 0.7rem',
              borderRadius: '999px',
              border: '1px solid rgba(99,102,241,0.18)',
              background: 'rgba(99,102,241,0.08)',
              color: '#6366f1',
              fontSize: '0.78rem',
              fontWeight: 600,
            }}
          >
            {attachedCount} attached document{attachedCount === 1 ? '' : 's'}
          </span>
        </div>
      ) : null}

      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: '0.65rem',
          background: 'rgba(17,24,39,0.94)',
          border: '1px solid rgba(148,163,184,0.18)',
          borderRadius: '24px',
          padding: '0.7rem 0.85rem 0.7rem 0.75rem',
          boxShadow: '0 24px 50px rgba(15,23,42,0.16)',
          transition: 'border-color 0.15s, transform 0.15s',
        }}
        onFocus={(e) => (e.currentTarget.style.borderColor = 'rgba(129,140,248,0.45)')}
        onBlur={(e) => (e.currentTarget.style.borderColor = 'rgba(148,163,184,0.18)')}
      >
        <button
          type="button"
          onClick={() => setMenuOpen((v) => !v)}
          disabled={disabled}
          aria-label="Add attachment or source"
          style={{
            width: 42,
            height: 42,
            borderRadius: '14px',
            border: '1px solid rgba(148,163,184,0.2)',
            background: menuOpen ? 'rgba(99,102,241,0.18)' : 'rgba(255,255,255,0.04)',
            color: '#e5e7eb',
            cursor: disabled ? 'not-allowed' : 'pointer',
            display: 'grid',
            placeItems: 'center',
            fontSize: '1.35rem',
            flexShrink: 0,
          }}
        >
          +
        </button>

        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder || 'Ask anything about transactions, vendors, policies, or uploaded documents...'}
          rows={1}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            resize: 'none',
            color: '#f9fafb',
            fontSize: '0.95rem',
            lineHeight: 1.6,
            fontFamily: 'inherit',
            minHeight: '26px',
            maxHeight: '160px',
            overflow: 'auto',
          }}
        />

        <button
          type="button"
          onClick={onSubmit}
          disabled={disabled || !value.trim()}
          style={{
            width: 44,
            height: 44,
            borderRadius: '16px',
            border: 'none',
            flexShrink: 0,
            background: disabled || !value.trim() ? 'rgba(148,163,184,0.22)' : 'linear-gradient(135deg, #6366f1, #22d3ee)',
            color: disabled || !value.trim() ? 'rgba(226,232,240,0.38)' : '#fff',
            cursor: disabled || !value.trim() ? 'not-allowed' : 'pointer',
            display: 'grid',
            placeItems: 'center',
            fontSize: '1rem',
            transition: 'all 0.15s',
            boxShadow: disabled || !value.trim() ? 'none' : '0 8px 18px rgba(79,70,229,0.28)',
          }}
        >
          {disabled ? '⏸' : '↑'}
        </button>
      </div>
    </div>
  );
}

function MenuAction({
  title,
  description,
  onClick,
}: {
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        width: '100%',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '0.85rem',
        padding: '0.75rem 0.85rem',
        border: 'none',
        borderRadius: '16px',
        background: 'transparent',
        color: '#f9fafb',
        cursor: 'pointer',
        textAlign: 'left',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent';
      }}
    >
      <span
        style={{
          width: 28,
          height: 28,
          borderRadius: '10px',
          background: 'rgba(99,102,241,0.16)',
          border: '1px solid rgba(129,140,248,0.28)',
          display: 'grid',
          placeItems: 'center',
          fontWeight: 800,
          color: '#a5b4fc',
          flexShrink: 0,
          marginTop: '0.1rem',
        }}
      >
        +
      </span>
      <span style={{ display: 'grid', gap: '0.18rem', minWidth: 0 }}>
        <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>{title}</span>
        <span style={{ fontSize: '0.78rem', color: '#cbd5e1', lineHeight: 1.45 }}>{description}</span>
      </span>
    </button>
  );
}
