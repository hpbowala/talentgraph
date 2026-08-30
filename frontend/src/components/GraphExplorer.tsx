import { useCallback, useEffect, useMemo, useState } from "react";
import { getGraph } from "../api";
import { relativeTime } from "../format";
import { NODE_TYPES, relationLabel, typeColor, typeLabel } from "../graph-theme";
import { GraphCanvas } from "./GraphCanvas";
import type { GraphSnapshot } from "../types";

interface Props {
  /** Node to open on, e.g. an entity picked out of a chat answer. */
  focus?: string | null;
  /** Bumped by the caller to re-apply `focus` even when it has not changed. */
  focusToken?: number;
  onCollapse: () => void;
}

/** How far from the selection "focus" mode keeps drawing. */
const FOCUS_HOPS = 1;

interface Connection {
  other: string;
  otherType: string;
  relation: string;
  /** false when the edge points at the selected node rather than away from it. */
  outgoing: boolean;
  evidence: string | null;
}

export function GraphExplorer({ focus, focusToken, onCollapse }: Props) {
  const [snapshot, setSnapshot] = useState<GraphSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(focus ?? null);
  const [query, setQuery] = useState("");
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [focusMode, setFocusMode] = useState(false);
  const [fitToken, setFitToken] = useState(0);
  const [appliedFocus, setAppliedFocus] = useState(focusToken ?? 0);

  // The pane stays mounted, so a focus request from chat has to be applied on
  // the way in. The token — not the id — is what marks a request as new, so
  // asking twice for the same node still lands. Adjusting during render keeps
  // it out of an effect, and so out of a second render pass.
  if ((focusToken ?? 0) !== appliedFocus) {
    setAppliedFocus(focusToken ?? 0);
    if (focus) {
      setSelected(focus);
      setQuery("");
      setFocusMode(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    getGraph()
      .then((data) => {
        if (!cancelled) setSnapshot(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load the knowledge graph.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && selected) setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected]);

  const allNodes = useMemo(() => snapshot?.nodes ?? [], [snapshot]);
  const allEdges = useMemo(() => snapshot?.edges ?? [], [snapshot]);

  /** Every connection of the selected node, both directions. */
  const connections = useMemo<Connection[]>(() => {
    if (!selected) return [];
    const typeOf = new Map(allNodes.map((n) => [n.id, n.type]));
    const found: Connection[] = [];
    for (const edge of allEdges) {
      if (edge.source === selected) {
        found.push({
          other: edge.target,
          otherType: typeOf.get(edge.target) ?? "unknown",
          relation: edge.relation,
          outgoing: true,
          evidence: edge.evidence ?? null,
        });
      } else if (edge.target === selected) {
        found.push({
          other: edge.source,
          otherType: typeOf.get(edge.source) ?? "unknown",
          relation: edge.relation,
          outgoing: false,
          evidence: edge.evidence ?? null,
        });
      }
    }
    found.sort((a, b) => a.relation.localeCompare(b.relation) || a.other.localeCompare(b.other));
    return found;
  }, [selected, allNodes, allEdges]);

  // Visible set: type filters first, then the focus neighbourhood if it is on.
  const { nodes, edges } = useMemo(() => {
    let visible = new Set(allNodes.filter((n) => !hidden.has(n.type)).map((n) => n.id));

    if (focusMode && selected && visible.has(selected)) {
      let frontier = new Set([selected]);
      const keep = new Set(frontier);
      for (let hop = 0; hop < FOCUS_HOPS; hop++) {
        const next = new Set<string>();
        for (const edge of allEdges) {
          if (frontier.has(edge.source) && visible.has(edge.target)) next.add(edge.target);
          if (frontier.has(edge.target) && visible.has(edge.source)) next.add(edge.source);
        }
        for (const id of next) keep.add(id);
        frontier = next;
      }
      visible = keep;
    }

    return {
      nodes: allNodes.filter((n) => visible.has(n.id)),
      edges: allEdges.filter((e) => visible.has(e.source) && visible.has(e.target)),
    };
  }, [allNodes, allEdges, hidden, focusMode, selected]);

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return new Set<string>();
    return new Set(nodes.filter((n) => n.id.toLowerCase().includes(needle)).map((n) => n.id));
  }, [query, nodes]);

  const results = useMemo(() => {
    if (matches.size === 0) return [];
    return nodes.filter((n) => matches.has(n.id)).slice(0, 8);
  }, [matches, nodes]);

  const toggleType = useCallback((type: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  const selectedNode = useMemo(
    () => allNodes.find((n) => n.id === selected) ?? null,
    [allNodes, selected],
  );

  const shownTypes = NODE_TYPES.filter((t) => (snapshot?.counts[t] ?? 0) > 0);
  const loading = !snapshot && !error;

  return (
    <section className="graph-panel" aria-labelledby="graph-panel-title">
      <header className="graph-head">
        <div>
          <div className="overline">Knowledge graph</div>
          <h2 id="graph-panel-title">
            The graph
            {snapshot && (
              <span className="graph-count">
                {snapshot.nodes.length} notes · {snapshot.edges.length} connections
              </span>
            )}
          </h2>
        </div>
        <button
          className="pane-collapse"
          aria-label="Collapse the graph"
          title="Collapse the graph"
          onClick={onCollapse}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <path
              d="M8.5 2.5L3.5 7l5 4.5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </header>

      <div className="graph-toolbar">
        <div className="graph-search">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.4" />
            <path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
          <input
            value={query}
            placeholder="Find a person, skill or project…"
            aria-label="Search the graph"
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <button className="graph-search-clear" aria-label="Clear search" onClick={() => setQuery("")}>
              ×
            </button>
          )}
          {results.length > 0 && (
            <div className="graph-results">
              {results.map((node) => (
                <button
                  key={node.id}
                  onClick={() => {
                    setSelected(node.id);
                    setQuery("");
                  }}
                >
                  <span className="dot" style={{ background: typeColor(node.type) }} />
                  <span className="graph-result-name">{node.id}</span>
                  <span className="graph-result-type">{typeLabel(node.type)}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="graph-tools">
          <button
            className={focusMode ? "graph-tool on" : "graph-tool"}
            disabled={!selected}
            title={
              selected
                ? "Show only the selected note and what it connects to"
                : "Select a note first"
            }
            aria-pressed={focusMode}
            onClick={() => setFocusMode((on) => !on)}
          >
            Focus
          </button>
          <button className="graph-tool" onClick={() => setFitToken((n) => n + 1)}>
            Fit
          </button>
        </div>
      </div>

      <div className="graph-legend">
        {shownTypes.map((type) => (
          <button
            key={type}
            className={hidden.has(type) ? "graph-chip off" : "graph-chip"}
            aria-pressed={!hidden.has(type)}
            onClick={() => toggleType(type)}
          >
            <span className="dot" style={{ background: typeColor(type) }} />
            {typeLabel(type)}
            <span className="graph-chip-count">{snapshot?.counts[type] ?? 0}</span>
          </button>
        ))}
      </div>

      <div className="graph-body">
        <div className="graph-stage">
          {loading && (
            <div className="graph-status">
              <span className="nodes">
                <span />
                <span />
                <span />
              </span>
              loading the graph…
            </div>
          )}
          {error && <div className="graph-status error">{error}</div>}
          {snapshot && nodes.length === 0 && (
            <div className="graph-status">Every note type is hidden — turn one back on.</div>
          )}
          {snapshot && nodes.length > 0 && (
            <GraphCanvas
              nodes={nodes}
              edges={edges}
              selected={selected}
              matches={matches}
              onSelect={setSelected}
              fitToken={fitToken}
            />
          )}
        </div>

        {selectedNode && (
          <aside className="graph-detail">
            <div className="graph-detail-head">
              <span className="graph-type-badge" style={{ color: typeColor(selectedNode.type) }}>
                <span className="dot" style={{ background: typeColor(selectedNode.type) }} />
                {typeLabel(selectedNode.type)}
              </span>
              <button
                className="graph-detail-close"
                aria-label="Clear selection"
                onClick={() => setSelected(null)}
              >
                ×
              </button>
            </div>
            <h3>{selectedNode.id}</h3>
            {selectedNode.role && <p className="graph-role">{selectedNode.role}</p>}
            <p className="graph-detail-meta">
              {connections.length} connection{connections.length === 1 ? "" : "s"}
              {selectedNode.path && <span className="graph-path">{selectedNode.path}</span>}
            </p>

            <div className="graph-connections">
              {connections.map((c, i) => (
                <button
                  key={`${c.relation}-${c.other}-${i}`}
                  className="graph-connection"
                  onClick={() => setSelected(c.other)}
                >
                  <span className="graph-relation">
                    {c.outgoing ? "→" : "←"} {relationLabel(c.relation)}
                  </span>
                  <span className="graph-connection-name">
                    <span className="dot" style={{ background: typeColor(c.otherType) }} />
                    {c.other}
                  </span>
                  {c.evidence && <span className="graph-evidence">“{c.evidence}”</span>}
                </button>
              ))}
              {connections.length === 0 && (
                <p className="graph-empty">Nothing links to this note yet.</p>
              )}
            </div>
          </aside>
        )}
      </div>

      <footer className="graph-foot">
        <span>Drag to pan · scroll to zoom · click a node for its connections</span>
        {snapshot?.indexed_at && <span>Built {relativeTime(snapshot.indexed_at)}</span>}
      </footer>
    </section>
  );
}