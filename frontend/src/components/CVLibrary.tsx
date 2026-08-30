import { useCallback, useEffect, useRef, useState } from "react";
import { deleteCV, listCVs, uploadCV } from "../api";
import { fileSize, relativeTime } from "../format";
import type { CVLibrary } from "../types";

const ACCEPT = ".pdf,.txt,.md";
const POLL_INTERVAL_MS = 4000;
const INDEX_TIMEOUT_MS = 6 * 60 * 1000;

interface Props {
  library: CVLibrary | null;
  loadError: boolean;
  onClose: () => void;
  onChange: (library: CVLibrary) => void;
}

type Busy = { verb: string; name: string; note?: string } | null;

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Manages the CV corpus. Writes are accepted straight away and the graph is
 *  rebuilt behind them, so the panel polls until the index stamp moves. */
export function CVLibraryPanel({ library, loadError, onClose, onChange }: Props) {
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  /** Poll until the server publishes an index newer than `before`; returns its
   *  stamp, or null if the rebuild outlasted our patience. */
  const awaitIndex = useCallback(
    async (before: string | null | undefined) => {
      const deadline = Date.now() + INDEX_TIMEOUT_MS;
      while (Date.now() < deadline) {
        await delay(POLL_INTERVAL_MS);
        try {
          const next = await listCVs();
          onChange(next);
          if (next.indexed_at && next.indexed_at !== before) return next.indexed_at;
        } catch {
          /* keep polling — the rebuild is still running somewhere */
        }
      }
      return null;
    },
    [onChange],
  );

  const upload = useCallback(
    async (files: File[]) => {
      if (busy || files.length === 0) return;
      setError(null);
      setConfirming(null);
      // Each upload triggers its own rebuild, so they go up one at a time and
      // the stamp is carried forward by hand — the prop is a render behind.
      let stamp = library?.indexed_at ?? null;
      for (const [i, file] of files.entries()) {
        const note = files.length > 1 ? `File ${i + 1} of ${files.length}` : undefined;
        setBusy({ verb: "Indexing", name: file.name, note });
        try {
          onChange(await uploadCV(file));
        } catch (err) {
          setError(err instanceof Error ? err.message : `Could not upload ${file.name}.`);
          break;
        }
        const indexed = await awaitIndex(stamp);
        if (!indexed) {
          setError(
            `${file.name} is still being indexed — it will appear once the graph is rebuilt.`,
          );
          break;
        }
        stamp = indexed;
      }
      setBusy(null);
    },
    [busy, library, onChange, awaitIndex],
  );

  const remove = useCallback(
    async (filename: string) => {
      if (busy) return;
      setError(null);
      setConfirming(null);
      const before = library?.indexed_at;
      setBusy({ verb: "Removing", name: filename });
      try {
        onChange(await deleteCV(filename));
      } catch (err) {
        setError(err instanceof Error ? err.message : `Could not remove ${filename}.`);
        setBusy(null);
        return;
      }
      if (!(await awaitIndex(before))) {
        setError("The graph is still rebuilding — it will catch up shortly.");
      }
      setBusy(null);
    },
    [busy, library, onChange, awaitIndex],
  );

  const cvs = library?.cvs ?? [];

  return (
    <div
      className="cv-overlay"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
    >
      <section
        className="cv-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cv-panel-title"
      >
        <header className="cv-head">
          <div>
            <div className="overline">Knowledge base</div>
            <h2 id="cv-panel-title">
              CV library
              <span className="cv-count">{cvs.length}</span>
            </h2>
          </div>
          <button
            className="cv-close"
            aria-label="Close CV library"
            title={busy ? "Indexing — this finishes on its own" : "Close"}
            disabled={!!busy}
            onClick={onClose}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path
                d="M3 3l8 8M11 3l-8 8"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </header>

        <p className="cv-intro">
          Every CV here is extracted into the knowledge graph. Add one and the graph is
          rebuilt around it; remove one and its entities go with it.
        </p>

        <div
          className={dragging ? "cv-drop dragging" : "cv-drop"}
          onDragOver={(e) => {
            e.preventDefault();
            if (!busy) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            void upload(Array.from(e.dataTransfer.files));
          }}
        >
          <input
            ref={fileInput}
            type="file"
            accept={ACCEPT}
            multiple
            hidden
            onChange={(e) => {
              void upload(Array.from(e.target.files ?? []));
              e.target.value = "";
            }}
          />
          {busy ? (
            <div className="cv-busy">
              <span className="nodes">
                <span />
                <span />
                <span />
              </span>
              <div>
                <strong>
                  {busy.verb} {busy.name}
                </strong>
                <span>
                  {busy.note ? `${busy.note} · ` : ""}
                  Rebuilding the graph around it — this can take a few minutes.
                </span>
              </div>
            </div>
          ) : (
            <>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M4 15v3a2 2 0 002 2h12a2 2 0 002-2v-3"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <p>
                Drop a CV here, or{" "}
                <button className="cv-browse" onClick={() => fileInput.current?.click()}>
                  browse your files
                </button>
              </p>
              <span className="cv-hint">PDF, TXT or Markdown · up to 4 MB each</span>
            </>
          )}
        </div>

        {error && <p className="cv-error">{error}</p>}
        {loadError && !error && (
          <p className="cv-error">Could not load the CV library from the service.</p>
        )}

        <div className="cv-list">
          {cvs.length === 0 && !loadError ? (
            <p className="cv-empty">No CVs indexed yet — upload one to build the graph.</p>
          ) : (
            cvs.map((cv) => (
              <div key={cv.filename} className="cv-item">
                <div className="cv-item-main">
                  <span className="cv-name">{cv.filename}</span>
                  <span className="cv-meta">
                    {cv.person ? <em>{cv.person}</em> : <em className="pending">not indexed</em>}
                    <span>{fileSize(cv.size_bytes)}</span>
                    <span>{relativeTime(cv.uploaded_at)}</span>
                  </span>
                </div>
                {confirming === cv.filename ? (
                  <div className="cv-confirm">
                    <button className="cv-confirm-yes" onClick={() => void remove(cv.filename)}>
                      Remove
                    </button>
                    <button className="cv-confirm-no" onClick={() => setConfirming(null)}>
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    className="cv-remove"
                    aria-label={`Remove ${cv.filename}`}
                    disabled={!!busy}
                    onClick={() => setConfirming(cv.filename)}
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
                )}
              </div>
            ))
          )}
        </div>

        {library?.indexed_at && (
          <footer className="cv-foot">Graph last rebuilt {relativeTime(library.indexed_at)}</footer>
        )}
      </section>
    </div>
  );
}
