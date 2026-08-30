import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent } from "react";
import {
  deleteConversation,
  getConversation,
  listConversations,
  listCVs,
  sendChat,
} from "../api";
import type {
  ConversationSummary,
  ConversationTurn,
  CVLibrary,
  Message,
} from "../types";
import { Brand, Sidebar } from "./Sidebar";
import { MessageView } from "./MessageView";
import { Composer } from "./Composer";
import { CVLibraryPanel } from "./CVLibrary";
import { GraphExplorer } from "./GraphExplorer";
import { useSession } from "../session-context";
import { trackSpotlight } from "../spotlight";

const EXAMPLES = [
  "Who has Python experience?",
  "Who has both Python and AWS?",
  "How is Alice connected to NLP?",
  "Who would suit a Python and AWS AI project?",
  "Build a three-person team for Python, AWS and React",
  "Why Alice over David for an AI project?",
  "Which people have overlapping skills?",
];

const ACTIVE_THREAD_KEY = "tg-conversation";
const LAYOUT_KEY = "tg-layout";

/** Share of the workspace the graph takes, in percent, while both panes are open. */
const DEFAULT_SPLIT = 62;
const MIN_SPLIT = 25;
const MAX_SPLIT = 80;

interface Layout {
  graphOpen: boolean;
  chatOpen: boolean;
  split: number;
}

const DEFAULT_LAYOUT: Layout = { graphOpen: true, chatOpen: true, split: DEFAULT_SPLIT };

function loadLayout(): Layout {
  try {
    const raw = localStorage.getItem(LAYOUT_KEY);
    if (!raw) return DEFAULT_LAYOUT;
    const saved = JSON.parse(raw) as Partial<Layout>;
    const layout: Layout = {
      graphOpen: saved.graphOpen ?? true,
      chatOpen: saved.chatOpen ?? true,
      split:
        typeof saved.split === "number"
          ? Math.min(MAX_SPLIT, Math.max(MIN_SPLIT, saved.split))
          : DEFAULT_SPLIT,
    };
    // Never restore into a workspace with nothing in it.
    if (!layout.graphOpen && !layout.chatOpen) return DEFAULT_LAYOUT;
    return layout;
  } catch {
    return DEFAULT_LAYOUT;
  }
}

function newConversationId(): string {
  return `web-${crypto.randomUUID()}`;
}

function loadConversationId(): string {
  try {
    const existing = localStorage.getItem(ACTIVE_THREAD_KEY);
    if (existing) return existing;
  } catch {
    /* storage unavailable */
  }
  return newConversationId();
}

function storeConversationId(id: string) {
  try {
    localStorage.setItem(ACTIVE_THREAD_KEY, id);
  } catch {
    /* ignore */
  }
}

function turnsToMessages(turns: ConversationTurn[]): Message[] {
  return turns.flatMap((t) => [
    { role: "user" as const, content: t.user },
    {
      role: "assistant" as const,
      content: t.answer,
      intent: t.intent,
      evidence: t.evidence,
    },
  ]);
}

export function Chat() {
  const { username, signOut } = useSession();
  const [conversationId, setConversationId] = useState(loadConversationId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [threads, setThreads] = useState<ConversationSummary[]>([]);
  const [threadsError, setThreadsError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [library, setLibrary] = useState<CVLibrary | null>(null);
  const [libraryError, setLibraryError] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [layout, setLayout] = useState<Layout>(loadLayout);
  const [dragging, setDragging] = useState(false);
  // The graph pane stays mounted; this is a request to select a node in it.
  // token rises on every request so asking twice for the same node still lands.
  const [graphFocus, setGraphFocus] = useState<{ id: string | null; token: number }>({
    id: null,
    token: 0,
  });
  const scrollRef = useRef<HTMLDivElement>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);

  const { graphOpen, chatOpen, split } = layout;

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading, chatOpen]);

  useEffect(() => {
    try {
      localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout));
    } catch {
      /* ignore */
    }
  }, [layout]);

  const refreshThreads = useCallback(async () => {
    try {
      setThreads(await listConversations());
      setThreadsError(false);
    } catch {
      setThreadsError(true);
    }
  }, []);

  const refreshLibrary = useCallback(async () => {
    try {
      setLibrary(await listCVs());
      setLibraryError(false);
    } catch {
      setLibraryError(true);
    }
  }, []);

  // On mount: load the thread list, the CV library and the last-active
  // transcript. RequireAuth guarantees a session before any of this runs.
  useEffect(() => {
    void refreshThreads();
    void refreshLibrary();
    let cancelled = false;
    getConversation(loadConversationId())
      .then((detail) => {
        if (!cancelled && detail) setMessages(turnsToMessages(detail.turns));
      })
      .catch(() => {
        /* fresh thread not on the server yet, or service unreachable */
      });
    return () => {
      cancelled = true;
    };
  }, [refreshThreads, refreshLibrary]);

  useEffect(() => {
    storeConversationId(conversationId);
  }, [conversationId]);

  // Collapsing one pane always leaves the other one open, so the workspace
  // can never end up empty.
  const toggleGraph = useCallback(() => {
    setLayout((prev) =>
      prev.graphOpen
        ? { ...prev, graphOpen: false, chatOpen: true }
        : { ...prev, graphOpen: true },
    );
    setMenuOpen(false);
  }, []);

  const toggleChat = useCallback(() => {
    setLayout((prev) =>
      prev.chatOpen
        ? { ...prev, chatOpen: false, graphOpen: true }
        : { ...prev, chatOpen: true },
    );
    setMenuOpen(false);
  }, []);

  const openGraph = useCallback((focus = "") => {
    setMenuOpen(false);
    setLayout((prev) => ({ ...prev, graphOpen: true }));
    setGraphFocus((prev) => ({ id: focus || null, token: prev.token + 1 }));
  }, []);

  const ask = useCallback(
    async (text: string) => {
      const question = text.trim();
      if (!question || loading) return;
      setMenuOpen(false);
      setMessages((prev) => [...prev, { role: "user", content: question }]);
      setLoading(true);
      try {
        const res = await sendChat(question, conversationId);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: res.answer,
            intent: res.intent,
            evidence: res.evidence,
          },
        ]);
        void refreshThreads();
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            role: "error",
            content:
              err instanceof Error
                ? err.message
                : "Could not reach the TalentGraph service.",
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [conversationId, loading, refreshThreads],
  );

  const openLibrary = useCallback(() => {
    setMenuOpen(false);
    setLibraryOpen(true);
    void refreshLibrary();
  }, [refreshLibrary]);

  const newChat = useCallback(() => {
    setConversationId(newConversationId());
    setMessages([]);
    setMenuOpen(false);
    setLayout((prev) => ({ ...prev, chatOpen: true }));
  }, []);

  const selectThread = useCallback(
    async (id: string) => {
      if (loading) return;
      setMenuOpen(false);
      setLayout((prev) => ({ ...prev, chatOpen: true }));
      if (id === conversationId) return;
      try {
        const detail = await getConversation(id);
        if (!detail) {
          // Deleted elsewhere — drop it from the list.
          setThreads((prev) => prev.filter((t) => t.conversation_id !== id));
          return;
        }
        setConversationId(id);
        setMessages(turnsToMessages(detail.turns));
      } catch {
        setThreadsError(true);
      }
    },
    [conversationId, loading],
  );

  const endSession = useCallback(() => {
    setMessages([]);
    setThreads([]);
    setLibrary(null);
    setMenuOpen(false);
    signOut();
  }, [signOut]);

  const deleteThread = useCallback(
    async (id: string) => {
      try {
        await deleteConversation(id);
        setThreads((prev) => prev.filter((t) => t.conversation_id !== id));
        if (id === conversationId) {
          setConversationId(newConversationId());
          setMessages([]);
        }
      } catch {
        setThreadsError(true);
      }
    },
    [conversationId],
  );

  // Divider drag. Pointer capture keeps the move events coming even when the
  // cursor outruns the 14px handle.
  const onDividerDown = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setDragging(true);
  }, []);

  const onDividerMove = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (!dragging) return;
      const box = workspaceRef.current?.getBoundingClientRect();
      if (!box || box.width === 0) return;
      const pct = ((e.clientX - box.left) / box.width) * 100;
      setLayout((prev) => ({
        ...prev,
        split: Math.min(MAX_SPLIT, Math.max(MIN_SPLIT, pct)),
      }));
    },
    [dragging],
  );

  const endDrag = useCallback(() => setDragging(false), []);

  const onDividerKey = useCallback((e: ReactKeyboardEvent<HTMLDivElement>) => {
    const step = e.key === "ArrowLeft" ? -4 : e.key === "ArrowRight" ? 4 : 0;
    if (!step) return;
    e.preventDefault();
    setLayout((prev) => ({
      ...prev,
      split: Math.min(MAX_SPLIT, Math.max(MIN_SPLIT, prev.split + step)),
    }));
  }, []);

  const bothOpen = graphOpen && chatOpen;
  const graphStyle = bothOpen ? { flex: `${split} 1 0%` } : undefined;
  const chatStyle = bothOpen ? { flex: `${100 - split} 1 0%` } : undefined;

  return (
    <div className="app">
      <div className="ambient" aria-hidden="true">
        <div className="blob blob-a" />
        <div className="blob blob-b" />
        <div className="blob blob-c" />
        <div className="blob blob-d" />
      </div>
      <header className="mobile-bar">
        <Brand />
        <button
          className="menu-toggle"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          )}
        </button>
      </header>
      <Sidebar
        threads={threads}
        activeId={conversationId}
        threadsError={threadsError}
        disabled={loading}
        open={menuOpen}
        cvCount={library?.cvs.length ?? 0}
        username={username}
        graphOpen={graphOpen}
        chatOpen={chatOpen}
        onNew={newChat}
        onToggleGraph={toggleGraph}
        onToggleChat={toggleChat}
        onOpenLibrary={openLibrary}
        onSelect={selectThread}
        onDelete={deleteThread}
        onSignOut={endSession}
      />
      <main className="workspace" ref={workspaceRef}>
        {graphOpen ? (
          <section className="pane pane-graph" style={graphStyle}>
            <GraphExplorer
              focus={graphFocus.id}
              focusToken={graphFocus.token}
              onCollapse={toggleGraph}
            />
          </section>
        ) : (
          <button
            className="pane-rail"
            aria-label="Expand the graph"
            title="Expand the graph"
            onClick={toggleGraph}
          >
            <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M5.6 6.4l4.8-2.3M5.4 9.3l5 2.2M4 8.6a1.9 1.9 0 100-3.8 1.9 1.9 0 000 3.8zM12 5.1a1.6 1.6 0 100-3.2 1.6 1.6 0 000 3.2zM12 14.1a1.6 1.6 0 100-3.2 1.6 1.6 0 000 3.2z"
                stroke="currentColor"
                strokeWidth="1.3"
                strokeLinejoin="round"
              />
            </svg>
            <span className="rail-label">Graph</span>
          </button>
        )}

        {bothOpen && (
          <div
            className={dragging ? "pane-divider dragging" : "pane-divider"}
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize the panels"
            aria-valuenow={Math.round(split)}
            aria-valuemin={MIN_SPLIT}
            aria-valuemax={MAX_SPLIT}
            tabIndex={0}
            onPointerDown={onDividerDown}
            onPointerMove={onDividerMove}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
            onKeyDown={onDividerKey}
            onDoubleClick={() => setLayout((prev) => ({ ...prev, split: DEFAULT_SPLIT }))}
          >
            <span />
          </div>
        )}

        {chatOpen ? (
          <section className="pane pane-chat" style={chatStyle}>
            <header className="pane-head">
              <div>
                <div className="overline">Assistant</div>
                <h2>Chat</h2>
              </div>
              <button
                className="pane-collapse"
                aria-label="Collapse the chat"
                title="Collapse the chat"
                onClick={toggleChat}
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                  <path
                    d="M5.5 2.5L10.5 7l-5 4.5"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </header>
            <div className="chat-scroll" ref={scrollRef}>
              <div className="chat-inner">
                {messages.length === 0 && !loading ? (
                  <div className="empty">
                    <h2>Ask the graph who can build what.</h2>
                    <div className="suggestions">
                      {EXAMPLES.map((q) => (
                        <button
                          key={q}
                          className="chip spot"
                          onClick={() => ask(q)}
                          onMouseMove={trackSpotlight}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  messages.map((m, i) => (
                    <MessageView key={i} message={m} onShowInGraph={openGraph} />
                  ))
                )}
                {loading && (
                  <div className="thinking">
                    <span className="nodes">
                      <span />
                      <span />
                      <span />
                    </span>
                    traversing the graph…
                  </div>
                )}
              </div>
            </div>
            <Composer disabled={loading} onSubmit={ask} />
          </section>
        ) : (
          <button
            className="pane-rail"
            aria-label="Expand the chat"
            title="Expand the chat"
            onClick={toggleChat}
          >
            <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M13.5 8.2c0 2.6-2.5 4.7-5.5 4.7-.7 0-1.4-.1-2-.3L2.5 13.7l1-2.6A4.4 4.4 0 012.5 8.2c0-2.6 2.5-4.7 5.5-4.7s5.5 2.1 5.5 4.7z"
                stroke="currentColor"
                strokeWidth="1.3"
                strokeLinejoin="round"
              />
            </svg>
            <span className="rail-label">Chat</span>
          </button>
        )}
      </main>
      {libraryOpen && (
        <CVLibraryPanel
          library={library}
          loadError={libraryError}
          onClose={() => setLibraryOpen(false)}
          onChange={(next) => {
            setLibrary(next);
            setLibraryError(false);
          }}
        />
      )}
    </div>
  );
}
