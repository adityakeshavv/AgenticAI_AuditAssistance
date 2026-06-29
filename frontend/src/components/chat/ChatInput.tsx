import { type FormEventHandler, useRef } from 'react';

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({ value, onChange, onSubmit, disabled, placeholder }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !disabled) onSubmit();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value);
    const ta = textareaRef.current;
    if (ta) { ta.style.height = 'auto'; ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`; }
  };

  return (
    <div style={{
      display: 'flex', alignItems: 'flex-end', gap: '0.65rem',
      background: 'var(--bg-card)', border: '1px solid var(--border-md)',
      borderRadius: '18px', padding: '0.65rem 0.75rem 0.65rem 1rem',
      boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
      transition: 'border-color 0.15s',
    }}
      onFocus={(e) => (e.currentTarget.style.borderColor = 'rgba(59,130,246,0.5)')}
      onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border-md)')}
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={placeholder || 'Ask an audit question… (Enter to send, Shift+Enter for newline)'}
        rows={1}
        style={{
          flex: 1, background: 'transparent', border: 'none', outline: 'none',
          resize: 'none', color: 'var(--text-primary)', fontSize: '0.92rem',
          lineHeight: 1.5, fontFamily: 'inherit',
          minHeight: '24px', maxHeight: '160px', overflow: 'auto',
        }}
      />
      <button
        type="button"
        onClick={onSubmit}
        disabled={disabled || !value.trim()}
        style={{
          width: 38, height: 38, borderRadius: '12px', border: 'none', flexShrink: 0,
          background: disabled || !value.trim() ? 'rgba(59,130,246,0.2)' : 'linear-gradient(135deg, #3b82f6, #2563eb)',
          color: disabled || !value.trim() ? 'rgba(147,197,253,0.4)' : '#fff',
          cursor: disabled || !value.trim() ? 'not-allowed' : 'pointer',
          display: 'grid', placeItems: 'center', fontSize: '1rem',
          transition: 'all 0.15s', boxShadow: disabled || !value.trim() ? 'none' : '0 4px 12px rgba(37,99,235,0.35)',
        }}
      >
        {disabled ? '⏸' : '↑'}
      </button>
    </div>
  );
}
