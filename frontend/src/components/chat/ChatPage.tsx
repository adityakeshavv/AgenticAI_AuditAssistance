import { useEffect, useRef, useState, type ChangeEvent } from 'react';

import type {
  ChatHistoryResponse,
  ChatMessage,
  ChatResponse,
  ChatSessionSummary,
  InvestigationState,
  SuggestedAction,
} from '../../types/audit';
import type { DocumentMetadataRecord } from '../../types/databaseConnections';
import { getStoredAuthUser } from '../../services/authApi';
import { createChatSession, getChatHistory, listChatSessions, sendChatMessage } from '../../services/auditApi';
import { uploadDocumentSource } from '../../services/databaseConnectionsApi';
import { getSelectedWorkspaceId } from '../../services/workspacesApi';
import { ChatBubble } from './ChatBubble';
import { ChatInput } from './ChatInput';
import { InvestigationSidebar } from './InvestigationSidebar';
import { SuggestedActions } from './SuggestedActions';

const SESSION_KEY = 'audit_chat_active_session_id';

const STARTER_QUERIES = [
  'Show flagged transactions above $50,000',
  'Investigate vendor VND-02731',
  'Review approval exceptions',
  'Explain the latest finding',
  'Summarize evidence for this case',
];

const EMPTY_INVESTIGATION: InvestigationState = {
  entity_ids: [],
  transaction_ids: [],
  topics: [],
  transaction_count: 0,
  document_count: 0,
  finding_count: 0,
  key_findings: [],
  recommendations: [],
  status: 'idle',
};

interface ChatPageProps {
  onNavigateToSources?: () => void;
  onNavigateToWorkspaces?: () => void;
}

interface SessionUiState {
  title?: string;
  pinned?: boolean;
  archived?: boolean;
  hidden?: boolean;
}

const SESSION_UI_KEY = 'audit_chat_session_ui_state';

function getFirstName(fullName?: string | null): string {
  if (!fullName) return 'there';
  return fullName.trim().split(/\s+/)[0] || 'there';
}

function toDocumentRecord(value: unknown): DocumentMetadataRecord | null {
  if (!value || typeof value !== 'object') return null;
  const document = value as Partial<DocumentMetadataRecord>;
  if (!document.document_id || !document.file_name) return null;
  return {
    document_id: document.document_id,
    document_type: document.document_type || 'document',
    document_category: document.document_category || 'uploaded',
    related_vendor_id: document.related_vendor_id ?? null,
    related_employee_id: document.related_employee_id ?? null,
    related_transaction_id: document.related_transaction_id ?? null,
    related_contract_id: document.related_contract_id ?? null,
    related_investigation_id: document.related_investigation_id ?? null,
    creation_date: document.creation_date || new Date().toISOString().slice(0, 10),
    file_name: document.file_name,
    file_path: document.file_path || '',
    source_uri: document.source_uri || '',
    source_metadata_file: document.source_metadata_file || '',
    created_at: document.created_at ?? null,
    updated_at: document.updated_at ?? null,
  };
}

function turnToMessages(history: ChatHistoryResponse): ChatMessage[] {
  const messages: ChatMessage[] = [];
  history.turns.forEach((turn) => {
    messages.push({
      id: `${turn.turn_id}-user`,
      role: 'user',
      content: turn.user_message,
      timestamp: turn.timestamp || new Date().toISOString(),
    });
    messages.push({
      id: `${turn.turn_id}-assistant`,
      role: 'assistant',
      content: turn.assistant_message || turn.response.assistant_message || turn.response.final_response || '',
      timestamp: turn.timestamp || new Date().toISOString(),
      response: {
        ...turn.response,
        session_id: turn.response.session_id || history.session_id,
        session_title: turn.response.session_title || history.session_title,
      },
    });
  });
  return messages;
}

function SessionGroup({
  title,
  sessions,
  activeSessionId,
  sessionUiState,
  sessionMenuOpen,
  setSessionMenuOpen,
  sessionMenuRefs,
  onSelectSession,
  onRenameSession,
  onShareSession,
  onPinSession,
  onArchiveSession,
  onDeleteSession,
  emptyLabel,
}: {
  title: string;
  sessions: ChatSessionSummary[];
  activeSessionId: string | null;
  sessionUiState: Record<string, SessionUiState>;
  sessionMenuOpen: string | null;
  setSessionMenuOpen: (sessionId: string | null) => void;
  sessionMenuRefs: React.MutableRefObject<Record<string, HTMLDivElement | null>>;
  onSelectSession: (id: string) => void;
  onRenameSession: (id: string) => void;
  onShareSession: (id: string) => void;
  onPinSession: (id: string) => void;
  onArchiveSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  emptyLabel: string;
}) {
  if (!sessions.length) {
    return (
      <div style={{ display: 'grid', gap: '0.5rem' }}>
        <p className="label" style={{ marginBottom: 0 }}>
          {title}
        </p>
        <div className="card" style={{ padding: '0.8rem 0.9rem', fontSize: '0.83rem', color: 'var(--text-muted)' }}>
          {emptyLabel}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gap: '0.5rem' }}>
      <p className="label" style={{ marginBottom: 0 }}>
        {title}
      </p>
      <div style={{ display: 'grid', gap: '0.55rem' }}>
        {sessions.map((session) => {
          const active = session.session_id === activeSessionId;
          const ui = sessionUiState[session.session_id] || {};
          const titleText = ui.title || session.session_title || 'New chat';
          const preview = truncatePreview(session.last_message_preview, 82);
          const dateText = session.last_message_at ? new Date(session.last_message_at).toLocaleDateString() : '';
          return (
            <div
              key={session.session_id}
              style={{
                position: 'relative',
                borderRadius: '18px',
                border: `1px solid ${active ? 'rgba(99,102,241,0.35)' : 'var(--border)'}`,
                background: active ? 'rgba(99,102,241,0.08)' : 'rgba(255,255,255,0.9)',
                boxShadow: active ? '0 10px 24px rgba(99,102,241,0.08)' : '0 8px 22px rgba(15,23,42,0.04)',
                overflow: 'visible',
                zIndex: sessionMenuOpen === session.session_id ? 20 : 1,
              }}
              onMouseLeave={() => setSessionMenuOpen(null)}
            >
              <button
                type="button"
                onClick={() => onSelectSession(session.session_id)}
                style={{
                  textAlign: 'left',
                  width: '100%',
                  padding: '0.82rem 2.35rem 0.82rem 0.9rem',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.6rem' }}>
                  <div style={{ minWidth: 0 }}>
                    <strong
                      style={{
                        display: 'block',
                        fontSize: '0.9rem',
                        color: 'var(--text-primary)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        maxWidth: '180px',
                      }}
                    >
                      {titleText}
                    </strong>
                    <span
                      className="small-copy"
                      style={{
                        display: '-webkit-box',
                        WebkitBoxOrient: 'vertical',
                        WebkitLineClamp: 2,
                        overflow: 'hidden',
                        marginTop: '0.25rem',
                        lineHeight: 1.45,
                      }}
                    >
                      {preview}
                    </span>
                  </div>
                  {ui.pinned && (
                    <span className="source-pill" style={{ fontSize: '0.68rem', flexShrink: 0 }}>
                      Pinned
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.55rem', gap: '0.5rem' }}>
                  <span className="source-pill">
                    {session.turn_count} turn{session.turn_count === 1 ? '' : 's'}
                  </span>
                  <span className="small-copy">{dateText}</span>
                </div>
              </button>

              <button
                type="button"
                aria-label="Chat options"
                onClick={() => setSessionMenuOpen(sessionMenuOpen === session.session_id ? null : session.session_id)}
                style={{
                  position: 'absolute',
                  top: '0.6rem',
                  right: '0.55rem',
                  width: '32px',
                  height: '32px',
                  borderRadius: '10px',
                  border: '1px solid rgba(148,163,184,0.2)',
                  background: sessionMenuOpen === session.session_id ? 'rgba(99,102,241,0.12)' : 'rgba(255,255,255,0.82)',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                }}
              >
                ⋯
              </button>

              {sessionMenuOpen === session.session_id && (
                <div
                  ref={(node) => {
                    sessionMenuRefs.current[session.session_id] = node;
                  }}
                  style={{
                    position: 'absolute',
                    top: '2.6rem',
                    right: '0.6rem',
                    minWidth: '180px',
                    padding: '0.35rem',
                    borderRadius: '16px',
                    border: '1px solid rgba(148,163,184,0.18)',
                    background: 'rgba(17,24,39,0.96)',
                    boxShadow: '0 18px 36px rgba(15,23,42,0.24)',
                    zIndex: 5,
                  }}
                >
                  <SessionMenuItem label="Rename" onClick={() => onRenameSession(session.session_id)} />
                  <SessionMenuItem label="Share" onClick={() => onShareSession(session.session_id)} />
                  <SessionMenuItem label={ui.pinned ? 'Unpin' : 'Pin'} onClick={() => onPinSession(session.session_id)} />
                  <SessionMenuItem label={ui.archived ? 'Unarchive' : 'Archive'} onClick={() => onArchiveSession(session.session_id)} />
                  <SessionMenuItem label="Delete" destructive onClick={() => onDeleteSession(session.session_id)} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SessionMenuItem({
  label,
  onClick,
  destructive,
}: {
  label: string;
  onClick: () => void;
  destructive?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        width: '100%',
        padding: '0.6rem 0.75rem',
        border: 'none',
        borderRadius: '12px',
        background: 'transparent',
        color: destructive ? '#fda4af' : '#f9fafb',
        cursor: 'pointer',
        textAlign: 'left',
        fontSize: '0.82rem',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent';
      }}
    >
      {label}
    </button>
  );
}

function loadSessionUiState(): Record<string, SessionUiState> {
  try {
    const raw = localStorage.getItem(SESSION_UI_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, SessionUiState>;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function persistSessionUiState(state: Record<string, SessionUiState>) {
  localStorage.setItem(SESSION_UI_KEY, JSON.stringify(state));
}

function truncatePreview(text: string | null | undefined, limit = 72): string {
  const cleaned = (text || '').replace(/\s+/g, ' ').trim();
  if (!cleaned) return 'No messages yet';
  if (cleaned.length <= limit) return cleaned;
  return `${cleaned.slice(0, limit - 1).trimEnd()}…`;
}

export function ChatPage({ onNavigateToSources, onNavigateToWorkspaces }: ChatPageProps = {}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(localStorage.getItem(SESSION_KEY));
  const [chatSessions, setChatSessions] = useState<ChatSessionSummary[]>([]);
  const [isSessionLoading, setIsSessionLoading] = useState(true);
  const [suggestedActions, setSuggestedActions] = useState<SuggestedAction[]>([]);
  const [investigationState, setInvestigationState] = useState<InvestigationState>(EMPTY_INVESTIGATION);
  const [turnCount, setTurnCount] = useState(0);
  const [showSidebar, setShowSidebar] = useState(false);
  const [attachedDocuments, setAttachedDocuments] = useState<DocumentMetadataRecord[]>([]);
  const [sessionUiState, setSessionUiState] = useState<Record<string, SessionUiState>>(loadSessionUiState());
  const [sessionMenuOpen, setSessionMenuOpen] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const sessionMenuRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const activeWorkspaceId = getSelectedWorkspaceId();
  const currentUser = getStoredAuthUser();
  const firstName = getFirstName(currentUser?.full_name);
  const activeSession = chatSessions.find((item) => item.session_id === sessionId) || null;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    persistSessionUiState(sessionUiState);
  }, [sessionUiState]);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      if (!sessionMenuOpen) return;
      const currentMenu = sessionMenuRefs.current[sessionMenuOpen];
      if (currentMenu && !currentMenu.contains(event.target as Node)) {
        setSessionMenuOpen(null);
      }
    };

    document.addEventListener('pointerdown', handlePointerDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
    };
  }, [sessionMenuOpen]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setIsSessionLoading(true);
      try {
        const sessions = await listChatSessions();
        if (cancelled) return;
        setChatSessions(sessions);

        const storedSessionId = localStorage.getItem(SESSION_KEY);
        const selected = sessions.find((item) => item.session_id === storedSessionId) || sessions[0] || null;
        if (selected) {
          await loadSessionHistory(selected.session_id);
        } else {
          setMessages([]);
          setSessionId(null);
          setTurnCount(0);
          setSuggestedActions([]);
          setInvestigationState(EMPTY_INVESTIGATION);
        }
      } catch {
        if (!cancelled) {
          setChatSessions([]);
        }
      } finally {
        if (!cancelled) {
          setIsSessionLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  const updateSessionSummary = (response: ChatResponse) => {
    if (!response.session_id) return;
    setSessionId(response.session_id);
    localStorage.setItem(SESSION_KEY, response.session_id);
    setTurnCount(response.turn_count);

    setChatSessions((prev) => {
      const nextTitle = response.session_title || 'New chat';
      const nextPreview =
        response.assistant_message ||
        response.final_response ||
        response.investigation_summary ||
        response.finding?.summary ||
        'New chat';
      const existing = prev.find((item) => item.session_id === response.session_id);
      const updated: ChatSessionSummary = {
        session_id: response.session_id,
        session_title: nextTitle,
        turn_count: response.turn_count,
        workspace_id: existing?.workspace_id ?? null,
        connection_id: existing?.connection_id ?? null,
        last_message_preview: nextPreview,
        created_at: existing?.created_at ?? null,
        updated_at: new Date().toISOString(),
        last_message_at: new Date().toISOString(),
        is_archived: false,
      };
      setSessionUiState((uiPrev) => ({
        ...uiPrev,
        [response.session_id]: {
          ...uiPrev[response.session_id],
          title: uiPrev[response.session_id]?.title || nextTitle,
          archived: false,
        },
      }));
      return [updated, ...prev.filter((item) => item.session_id !== response.session_id)];
    });
  };

  const loadSessionHistory = async (id: string) => {
    const history = await getChatHistory(id);
    setSessionId(history.session_id);
    localStorage.setItem(SESSION_KEY, history.session_id);
    setMessages(turnToMessages(history));
    setTurnCount(history.turn_count);
    const lastTurn = history.turns[history.turns.length - 1];
    setSuggestedActions(lastTurn?.response?.suggested_actions || []);
    setInvestigationState(lastTurn?.response?.investigation_state || EMPTY_INVESTIGATION);
  };

  const handleSelectSession = async (id: string) => {
    if (id === sessionId) return;
    setSessionMenuOpen(null);
    await loadSessionHistory(id);
  };

  const handleNewSession = async () => {
    const created = await createChatSession();
    setChatSessions((prev) => [created, ...prev.filter((item) => item.session_id !== created.session_id)]);
    setSessionId(created.session_id);
    localStorage.setItem(SESSION_KEY, created.session_id);
    setMessages([]);
    setInput('');
    setSuggestedActions([]);
    setInvestigationState(EMPTY_INVESTIGATION);
    setTurnCount(0);
    setUploadError(null);
    setAttachedDocuments([]);
  };

  const updateSessionUiState = (sessionIdToUpdate: string, updater: (prev: SessionUiState) => SessionUiState) => {
    setSessionUiState((prev) => ({
      ...prev,
      [sessionIdToUpdate]: updater(prev[sessionIdToUpdate] || {}),
    }));
  };

  const handleRenameSession = (targetSessionId: string) => {
    const current = sessionUiState[targetSessionId]?.title || chatSessions.find((item) => item.session_id === targetSessionId)?.session_title || 'New chat';
    const next = window.prompt('Rename this chat', current)?.trim();
    if (!next) return;
    updateSessionUiState(targetSessionId, (prev) => ({ ...prev, title: next }));
    setChatSessions((prev) =>
      prev.map((item) =>
        item.session_id === targetSessionId
          ? { ...item, session_title: next, updated_at: new Date().toISOString() }
          : item,
      ),
    );
    setSessionMenuOpen(null);
  };

  const handleShareSession = async (targetSessionId: string) => {
    const session = chatSessions.find((item) => item.session_id === targetSessionId);
    const title = sessionUiState[targetSessionId]?.title || session?.session_title || 'Chat';
    const shareText = `${title}\nSession: ${targetSessionId}`;
    try {
      await navigator.clipboard.writeText(shareText);
    } catch {
      window.prompt('Copy chat reference', shareText);
    }
    setSessionMenuOpen(null);
  };

  const handlePinSession = (targetSessionId: string) => {
    updateSessionUiState(targetSessionId, (prev) => ({ ...prev, pinned: !prev.pinned }));
    setSessionMenuOpen(null);
  };

  const handleArchiveSession = (targetSessionId: string) => {
    updateSessionUiState(targetSessionId, (prev) => ({ ...prev, archived: !prev.archived }));
    if (targetSessionId === sessionId) {
      setSessionId(null);
      setMessages([]);
      setSuggestedActions([]);
      setInvestigationState(EMPTY_INVESTIGATION);
      setTurnCount(0);
      setInput('');
    }
    setSessionMenuOpen(null);
  };

  const handleDeleteSession = (targetSessionId: string) => {
    const session = chatSessions.find((item) => item.session_id === targetSessionId);
    const title = sessionUiState[targetSessionId]?.title || session?.session_title || 'this chat';
    const confirmed = window.confirm(`Delete ${title}? This removes it from your local chat list.`);
    if (!confirmed) return;
    updateSessionUiState(targetSessionId, (prev) => ({ ...prev, hidden: true }));
    setChatSessions((prev) => prev.filter((item) => item.session_id !== targetSessionId));
    if (targetSessionId === sessionId) {
      setSessionId(null);
      setMessages([]);
      setSuggestedActions([]);
      setInvestigationState(EMPTY_INVESTIGATION);
      setTurnCount(0);
      setInput('');
    }
    setSessionMenuOpen(null);
  };

  const visibleSessions = chatSessions.filter((session) => !sessionUiState[session.session_id]?.hidden && !sessionUiState[session.session_id]?.archived);
  const archivedSessions = chatSessions.filter((session) => sessionUiState[session.session_id]?.archived && !sessionUiState[session.session_id]?.hidden);
  const pinnedSessions = visibleSessions.filter((session) => sessionUiState[session.session_id]?.pinned);
  const recentSessions = visibleSessions.filter((session) => !sessionUiState[session.session_id]?.pinned);

  const appendAssistantResponse = (response: ChatResponse) => {
    updateSessionSummary(response);

    if (response.investigation_state) {
      setInvestigationState(response.investigation_state);
    }

    if (response.suggested_actions?.length) {
      setSuggestedActions(response.suggested_actions);
    } else {
      setSuggestedActions([]);
    }

    const summary =
      response.conversation_mode && response.conversation_mode !== 'audit'
        ? response.assistant_message || response.final_response || 'Conversation response.'
        : response.investigation_summary ||
          response.transaction_summary ||
          response.vendor_summary ||
          response.finding?.summary ||
          response.final_response ||
          'Investigation complete.';

    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: String(summary),
      timestamp: new Date().toISOString(),
      response,
    };

    setMessages((prev) => [...prev.slice(0, -1), assistantMsg]);
  };

  const sendMessage = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    setInput('');
    setUploadError(null);

    let activeSessionId = sessionId;
    if (!activeSessionId) {
      const created = await createChatSession();
      setChatSessions((prev) => [created, ...prev.filter((item) => item.session_id !== created.session_id)]);
      activeSessionId = created.session_id;
      setSessionId(created.session_id);
      localStorage.setItem(SESSION_KEY, created.session_id);
    }

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    };
    const loadingMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      isLoading: true,
    };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setIsLoading(true);
    setSuggestedActions([]);

    try {
      const response: ChatResponse = await sendChatMessage(
        trimmed,
        activeSessionId,
        attachedDocuments.map((document) => document.document_id),
      );
      appendAssistantResponse(response);
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'An error occurred. Please try again.'}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev.slice(0, -1), errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleActionSelect = (action: SuggestedAction) => {
    void sendMessage(action.description || action.label);
  };

  const handleAttachClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    if (!files.length) return;

    setIsUploading(true);
    setUploadError(null);

    try {
      const uploaded: DocumentMetadataRecord[] = [];
      for (const file of files) {
        const result = await uploadDocumentSource({ file });
        const record = toDocumentRecord(result.document);
        if (record) {
          uploaded.push(record);
        }
      }
      if (uploaded.length > 0) {
        setAttachedDocuments((prev) => [...prev, ...uploaded]);
      }
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Failed to upload document.');
    } finally {
      setIsUploading(false);
    }
  };

  const hasMessages = messages.length > 0;

  return (
    <div style={{ display: 'flex', gap: '1rem', height: 'calc(100vh - 60px)', overflow: 'hidden', minWidth: 0 }}>
      <aside
        style={{
          width: 290,
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: '0.85rem',
          minWidth: 0,
          padding: '1rem 0 1rem 1rem',
          borderRight: '1px solid rgba(226,232,240,0.9)',
          background: 'rgba(255,255,255,0.88)',
          backdropFilter: 'blur(14px)',
        }}
      >
        <div
          style={{
            padding: '0.95rem',
            borderRadius: '18px',
            border: '1px solid var(--border)',
            background: 'linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.92))',
            boxShadow: '0 12px 30px rgba(15,23,42,0.05)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
            <div>
              <p className="eyebrow" style={{ margin: 0 }}>
                Chats
              </p>
              <h3 style={{ margin: '0.15rem 0 0', fontSize: '1rem' }}>Saved sessions</h3>
            </div>
            <button type="button" className="btn btn-secondary" onClick={() => void handleNewSession()} style={{ fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
              New chat
            </button>
          </div>
          <p className="small-copy" style={{ marginTop: '0.5rem' }}>
            Conversations are stored per session so you can return to them later.
          </p>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', paddingRight: '0.2rem' }}>
          {isSessionLoading ? (
            <div className="card" style={{ padding: '0.9rem' }}>
              Loading chats...
            </div>
          ) : chatSessions.length > 0 ? (
            <div style={{ display: 'grid', gap: '1rem' }}>
              <SessionGroup
                title="Pinned"
                sessions={pinnedSessions}
                activeSessionId={sessionId}
                sessionUiState={sessionUiState}
                sessionMenuOpen={sessionMenuOpen}
                setSessionMenuOpen={setSessionMenuOpen}
                sessionMenuRefs={sessionMenuRefs}
                onSelectSession={handleSelectSession}
                onRenameSession={handleRenameSession}
                onShareSession={handleShareSession}
                onPinSession={handlePinSession}
                onArchiveSession={handleArchiveSession}
                onDeleteSession={handleDeleteSession}
                emptyLabel="Pin chats to keep them at the top."
              />
              <SessionGroup
                title="Recent"
                sessions={recentSessions}
                activeSessionId={sessionId}
                sessionUiState={sessionUiState}
                sessionMenuOpen={sessionMenuOpen}
                setSessionMenuOpen={setSessionMenuOpen}
                sessionMenuRefs={sessionMenuRefs}
                onSelectSession={handleSelectSession}
                onRenameSession={handleRenameSession}
                onShareSession={handleShareSession}
                onPinSession={handlePinSession}
                onArchiveSession={handleArchiveSession}
                onDeleteSession={handleDeleteSession}
                emptyLabel="Your recent chats will show up here."
              />
              {archivedSessions.length > 0 && (
                <SessionGroup
                  title="Archived"
                  sessions={archivedSessions}
                  activeSessionId={sessionId}
                  sessionUiState={sessionUiState}
                  sessionMenuOpen={sessionMenuOpen}
                  setSessionMenuOpen={setSessionMenuOpen}
                  sessionMenuRefs={sessionMenuRefs}
                  onSelectSession={handleSelectSession}
                  onRenameSession={handleRenameSession}
                  onShareSession={handleShareSession}
                  onPinSession={handlePinSession}
                  onArchiveSession={handleArchiveSession}
                  onDeleteSession={handleDeleteSession}
                  emptyLabel="Archived chats are tucked away here."
                />
              )}
            </div>
          ) : (
            <div className="card" style={{ padding: '0.95rem' }}>
              No saved chats yet. Start a new session to begin.
            </div>
          )}
        </div>
      </aside>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            padding: '0.95rem 1.2rem',
            borderBottom: '1px solid var(--border)',
            background: 'rgba(255,255,255,0.95)',
            backdropFilter: 'blur(10px)',
            flexShrink: 0,
          }}
        >
          <div>
            <p className="eyebrow" style={{ margin: 0 }}>
              Audit Copilot
            </p>
            <h2 style={{ margin: '0.12rem 0 0', fontSize: '1.02rem', fontWeight: 700 }}>
              {sessionId ? activeSession?.session_title || `Session ${turnCount > 0 ? `· Turn ${turnCount}` : ''}` : `Hi ${firstName}`}
            </h2>
            <p className="small-copy" style={{ marginTop: '0.2rem' }}>
              {activeWorkspaceId ? `Workspace scoped · ${activeWorkspaceId}` : 'No workspace selected'}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            {sessionId && (
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>{sessionId.slice(0, 8)}</span>
            )}
            <button type="button" className="btn btn-ghost" onClick={() => setShowSidebar((value) => !value)} style={{ fontSize: '0.8rem' }}>
              {showSidebar ? 'Close details' : 'Details'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => void handleNewSession()} style={{ fontSize: '0.8rem' }}>
              New session
            </button>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '1.1rem 1.1rem 0' }}>
          {!hasMessages ? (
            <div style={{ maxWidth: 780, margin: '2.5rem auto', textAlign: 'center' }}>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 84,
                  height: 84,
                  borderRadius: '28px',
                  background: 'linear-gradient(135deg, rgba(37,99,235,0.12), rgba(56,189,248,0.14))',
                  border: '1px solid rgba(37,99,235,0.18)',
                  boxShadow: '0 20px 40px rgba(37,99,235,0.08)',
                  marginBottom: '1rem',
                  animation: 'glowPulse 2.8s ease-in-out infinite',
                }}
              >
                <span style={{ fontSize: '2rem' }}>A</span>
              </div>
              <style>{`
                @keyframes glowPulse {
                  0%, 100% { transform: scale(1); box-shadow: 0 20px 40px rgba(37,99,235,0.08); }
                  50% { transform: scale(1.03); box-shadow: 0 24px 52px rgba(37,99,235,0.16); }
                }
              `}</style>
              <h2 style={{ fontSize: '1.55rem', fontWeight: 800, marginBottom: '0.5rem' }}>
                Hi {firstName}, let’s begin.
              </h2>
              <p className="body-copy" style={{ marginBottom: '1.5rem', color: 'var(--text-secondary)' }}>
                Ask me about transactions, vendors, evidence, compliance, or upload a document and I’ll keep the audit context flowing.
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.6rem', justifyContent: 'center', marginBottom: '1.25rem' }}>
                {['Start with transactions', 'Review a vendor', 'Explain a finding', 'Upload a document'].map((label) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => {
                      if (label === 'Upload a document') {
                        handleAttachClick();
                        return;
                      }
                      void sendMessage(label);
                    }}
                    className="source-pill"
                    style={{ cursor: 'pointer', border: '1px solid rgba(37,99,235,0.2)', background: 'rgba(37,99,235,0.05)' }}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem', textAlign: 'left' }}>
                {STARTER_QUERIES.map((query) => (
                  <button
                    key={query}
                    type="button"
                    onClick={() => void sendMessage(query)}
                    style={{
                      padding: '0.74rem 0.95rem',
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-md)',
                      color: 'var(--text-primary)',
                      fontSize: '0.88rem',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.15s',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.65rem',
                    }}
                  >
                    <span style={{ color: 'var(--accent-blue)', flexShrink: 0 }}>-&gt;</span>
                    {query}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ maxWidth: 920, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '0.75rem', paddingBottom: '1rem' }}>
              {messages.map((message) => (
                <ChatBubble key={message.id} msg={message} />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <div
          style={{
            padding: '0.7rem 1.1rem 0.95rem',
            borderTop: '1px solid var(--border)',
            background: 'rgba(255,255,255,0.96)',
            backdropFilter: 'blur(10px)',
            flexShrink: 0,
          }}
        >
          <div style={{ maxWidth: 920, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.doc,.docx,.txt,.eml,.md,.csv,.xlsx,.xls"
              onChange={handleFileUpload}
              style={{ display: 'none' }}
            />

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              {attachedDocuments.length > 0 && <span className="source-pill" style={{ fontSize: '0.72rem' }}>{attachedDocuments.length} attached</span>}
              {suggestedActions.length > 0 && <span className="source-pill" style={{ fontSize: '0.72rem' }}>{suggestedActions.length} next steps</span>}
              {uploadError && (
                <span
                  style={{
                    fontSize: '0.76rem',
                    color: 'var(--accent-red)',
                    background: 'rgba(239,68,68,0.08)',
                    border: '1px solid rgba(239,68,68,0.15)',
                    borderRadius: '999px',
                    padding: '0.35rem 0.65rem',
                  }}
                >
                  {uploadError}
                </span>
              )}
            </div>

            {suggestedActions.length > 0 && (
              <div
                style={{
                  padding: '0.75rem 0.9rem',
                  borderRadius: '18px',
                  border: '1px solid rgba(99,102,241,0.12)',
                  background: 'rgba(99,102,241,0.04)',
                }}
              >
                <p style={{ margin: '0 0 0.55rem', fontSize: '0.76rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                  What would you like to do next?
                </p>
                <SuggestedActions actions={suggestedActions} onSelect={handleActionSelect} disabled={isLoading} />
              </div>
            )}

            <ChatInput
              value={input}
              onChange={setInput}
              onSubmit={() => void sendMessage(input)}
              disabled={isLoading}
              attachedCount={attachedDocuments.length}
              onAttachDocuments={handleAttachClick}
              onOpenSources={onNavigateToSources}
              onOpenWorkspaces={onNavigateToWorkspaces}
            />
          </div>
        </div>
      </div>

      {showSidebar && (
        <div
          style={{
            position: 'fixed',
            top: '72px',
            right: '1rem',
            bottom: '1rem',
            width: '360px',
            zIndex: 35,
            pointerEvents: 'auto',
          }}
        >
          <div
            style={{
              height: '100%',
              borderRadius: '24px',
              border: '1px solid rgba(226,232,240,0.9)',
              background: 'rgba(255,255,255,0.96)',
              boxShadow: '0 24px 60px rgba(15,23,42,0.18)',
              backdropFilter: 'blur(18px)',
              overflow: 'hidden',
            }}
          >
            <InvestigationSidebar state={investigationState} turnCount={turnCount} onCollapse={() => setShowSidebar(false)} />
          </div>
        </div>
      )}
    </div>
  );
}
