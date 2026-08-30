import { relativeTime } from "../format";
import type { ConversationSummary } from "../types";

export function Brand() {
  return (
    <div className="brand">
      <img src="/graph.svg" alt="" />
      <div>
        <h1>
          Talent<span>Graph</span>
        </h1>
        <p>Conversational KG</p>
      </div>
    </div>
  );
}

interface Props {
  threads: ConversationSummary[];
  activeId: string;
  threadsError: boolean;
  disabled: boolean;
  open: boolean;
  cvCount: number;
  /** Signed-in account, or null when auth is not configured (local dev). */
  username: string | null;
  graphOpen: boolean;
  chatOpen: boolean;
  onNew: () => void;
  onToggleGraph: () => void;
  onToggleChat: () => void;
  onOpenLibrary: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onSignOut: () => void;
}

export function Sidebar({
  threads,
  activeId,
  threadsError,
  disabled,
  open,
  cvCount,
  username,
  graphOpen,
  chatOpen,
  onNew,
  onToggleGraph,
  onToggleChat,
  onOpenLibrary,
  onSelect,
  onDelete,
  onSignOut,
}: Props) {
  return (
    <aside className={open ? "sidebar open" : "sidebar"}>
      <Brand />

      <div className="sidebar-actions">
        <button className="new-conversation" onClick={onNew}>
          New chat
        </button>
        <div className="pane-switches">
          <button
            className={graphOpen ? "pane-switch on" : "pane-switch"}
            aria-pressed={graphOpen}
            onClick={onToggleGraph}
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M5.6 6.4l4.8-2.3M5.4 9.3l5 2.2M4 8.6a1.9 1.9 0 100-3.8 1.9 1.9 0 000 3.8zM12 5.1a1.6 1.6 0 100-3.2 1.6 1.6 0 000 3.2zM12 14.1a1.6 1.6 0 100-3.2 1.6 1.6 0 000 3.2z"
                stroke="currentColor"
                strokeWidth="1.3"
                strokeLinejoin="round"
              />
            </svg>
            Graph
          </button>
          <button
            className={chatOpen ? "pane-switch on" : "pane-switch"}
            aria-pressed={chatOpen}
            onClick={onToggleChat}
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M13.5 8.2c0 2.6-2.5 4.7-5.5 4.7-.7 0-1.4-.1-2-.3L2.5 13.7l1-2.6A4.4 4.4 0 012.5 8.2c0-2.6 2.5-4.7 5.5-4.7s5.5 2.1 5.5 4.7z"
                stroke="currentColor"
                strokeWidth="1.3"
                strokeLinejoin="round"
              />
            </svg>
            Chat
          </button>
        </div>
        <button className="cv-library-open" onClick={onOpenLibrary}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="M4 2h5l3 3v9H4V2z"
              stroke="currentColor"
              strokeWidth="1.3"
              strokeLinejoin="round"
            />
            <path d="M9 2v3h3" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
          </svg>
          CV library
          <span className="cv-library-count">{cvCount}</span>
        </button>
      </div>

      <div className="threads-section">
        <h2>Threads</h2>
        {threadsError ? (
          <p className="threads-note">Could not load chat history.</p>
        ) : threads.length === 0 ? (
          <p className="threads-note">No conversations yet.</p>
        ) : (
          <div className="threads">
            {threads.map((t) => (
              <div
                key={t.conversation_id}
                className={
                  t.conversation_id === activeId ? "thread-item active" : "thread-item"
                }
              >
                <button
                  className="thread-select"
                  disabled={disabled}
                  onClick={() => onSelect(t.conversation_id)}
                >
                  <span className="thread-title">{t.title}</span>
                  <span className="thread-time">{relativeTime(t.updated_at)}</span>
                </button>
                <button
                  className="thread-delete"
                  aria-label={`Delete "${t.title}"`}
                  disabled={disabled}
                  onClick={() => onDelete(t.conversation_id)}
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                    <path
                      d="M2.5 2.5l7 7M9.5 2.5l-7 7"
                      stroke="currentColor"
                      strokeWidth="1.4"
                      strokeLinecap="round"
                    />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {username && (
        <div className="sidebar-account">
          <span className="account-name" title={username}>
            {username}
          </span>
          <button className="sign-out" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      )}
    </aside>
  );
}
