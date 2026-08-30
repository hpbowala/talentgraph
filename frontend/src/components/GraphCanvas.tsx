import { useCallback, useEffect, useRef, useState } from "react";
import { Simulation, type SimNode } from "../graph-layout";
import { typeColor } from "../graph-theme";
import type { GraphEdge, GraphNode } from "../types";

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selected: string | null;
  /** Nodes matching the search box — ringed, with everything else dimmed. */
  matches: Set<string>;
  onSelect: (id: string | null) => void;
  /** Bumped by the parent to re-fit the view (the "Fit" button). */
  fitToken: number;
}

interface View {
  x: number;
  y: number;
  k: number;
}

const MIN_ZOOM = 0.15;
const MAX_ZOOM = 4;
/** Above this zoom every node is labelled; below it only the notable ones. */
const LABEL_ALL_ZOOM = 1.5;
const LABEL_DEGREE = 8;
const DRAG_THRESHOLD_PX = 3;
/** Fraction of nodes ignored at each edge when framing — see Simulation.bounds. */
const OUTLIER_TRIM = 0.02;
/** Relation names appear only once the view is close enough to read them. */
const RELATION_LABEL_ZOOM = 0.75;
/** How far along the edge, away from the focused node, a relation name sits. */
const RELATION_LABEL_ALONG = 0.62;

/**
 * Canvas rendering of the knowledge graph.
 *
 * The simulation and the view transform live in refs rather than state: they
 * change every animation frame, and re-rendering React sixty times a second to
 * move some circles would be the one thing this component must not do. React
 * state here is only what the surrounding DOM shows — the hover tooltip.
 */
export function GraphCanvas({ nodes, edges, selected, matches, onSelect, fitToken }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState<SimNode | null>(null);

  const simRef = useRef<Simulation | null>(null);
  // Carried across rebuilds so filtering nudges the layout rather than
  // scattering it.
  const positionsRef = useRef<Map<string, { x: number; y: number }>>(new Map());
  const adjacencyRef = useRef<Map<string, Set<string>>>(new Map());
  const viewRef = useRef<View>({ x: 0, y: 0, k: 1 });
  const dirtyRef = useRef(true);
  /** Set once the viewer pans or zooms; auto-framing then stops interfering. */
  const viewOwnedRef = useRef(false);

  // Read by the render loop each frame; kept in refs so updating them repaints
  // the canvas without re-rendering the component.
  const selectedRef = useRef(selected);
  const hoveredRef = useRef<string | null>(null);
  const matchesRef = useRef(matches);

  useEffect(() => {
    selectedRef.current = selected;
    dirtyRef.current = true;
  }, [selected]);

  useEffect(() => {
    matchesRef.current = matches;
    dirtyRef.current = true;
  }, [matches]);

  const toGraph = useCallback((clientX: number, clientY: number) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    const view = viewRef.current;
    return {
      x: (clientX - rect.left - rect.width / 2 - view.x) / view.k,
      y: (clientY - rect.top - rect.height / 2 - view.y) / view.k,
    };
  }, []);

  /** Frame the whole graph in the viewport. */
  const fit = useCallback(() => {
    const canvas = canvasRef.current;
    const sim = simRef.current;
    if (!canvas || !sim) return;
    const { minX, minY, maxX, maxY } = sim.bounds(OUTLIER_TRIM);
    const pad = 40;
    const k = Math.min(
      MAX_ZOOM,
      Math.max(
        MIN_ZOOM,
        Math.min(
          (canvas.clientWidth - pad * 2) / (maxX - minX || 1),
          (canvas.clientHeight - pad * 2) / (maxY - minY || 1),
        ),
      ),
    );
    viewRef.current = { k, x: -((minX + maxX) / 2) * k, y: -((minY + maxY) / 2) * k };
    dirtyRef.current = true;
  }, []);

  /** Build the simulation for the visible graph and run the render loop. */
  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;

    const sim = new Simulation(nodes, edges, positionsRef.current);
    simRef.current = sim;
    positionsRef.current = sim.positions();

    const adjacency = new Map<string, Set<string>>();
    for (const edge of edges) {
      if (!adjacency.has(edge.source)) adjacency.set(edge.source, new Set());
      if (!adjacency.has(edge.target)) adjacency.set(edge.target, new Set());
      adjacency.get(edge.source)!.add(edge.target);
      adjacency.get(edge.target)!.add(edge.source);
    }
    adjacencyRef.current = adjacency;

    let frame = 0;
    let framed = false;
    let settledOnce = false;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const { clientWidth, clientHeight } = wrap;
      canvas.width = Math.max(1, Math.round(clientWidth * dpr));
      canvas.height = Math.max(1, Math.round(clientHeight * dpr));
      canvas.style.width = `${clientWidth}px`;
      canvas.style.height = `${clientHeight}px`;
      dirtyRef.current = true;
      if (!framed && clientWidth > 0) {
        // First real measurement — only now can the view be framed.
        framed = true;
        fit();
      }
    };

    const observer = new ResizeObserver(resize);
    observer.observe(wrap);
    resize();

    const draw = () => {
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const dpr = window.devicePixelRatio || 1;
      const width = canvas.width / dpr;
      const height = canvas.height / dpr;
      const view = viewRef.current;
      const focusId = hoveredRef.current ?? selectedRef.current;
      const neighbours = focusId ? adjacency.get(focusId) : undefined;
      const searchMatches = matchesRef.current;
      const searching = searchMatches.size > 0;
      const lit = (id: string) => !focusId || id === focusId || !!neighbours?.has(id);

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);
      ctx.translate(width / 2 + view.x, height / 2 + view.y);
      ctx.scale(view.k, view.k);

      // edges
      for (const link of sim.links) {
        const active = focusId === link.source.id || focusId === link.target.id;
        if (active) {
          ctx.strokeStyle = "rgba(160, 170, 255, 0.55)";
          ctx.lineWidth = 1.6 / view.k;
        } else {
          ctx.strokeStyle = focusId ? "rgba(255, 255, 255, 0.03)" : "rgba(255, 255, 255, 0.09)";
          ctx.lineWidth = 1 / view.k;
        }
        ctx.beginPath();
        ctx.moveTo(link.source.x, link.source.y);
        ctx.lineTo(link.target.x, link.target.y);
        ctx.stroke();
      }

      // nodes
      for (const node of sim.nodes) {
        const dimmed = !lit(node.id) || (searching && !searchMatches.has(node.id));
        ctx.globalAlpha = dimmed ? 0.16 : 1;
        ctx.fillStyle = typeColor(node.type);
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
        ctx.fill();

        if (node.id === selectedRef.current) {
          ctx.globalAlpha = 1;
          ctx.strokeStyle = "#ffffff";
          ctx.lineWidth = 2 / view.k;
          ctx.beginPath();
          ctx.arc(node.x, node.y, node.r + 4 / view.k, 0, Math.PI * 2);
          ctx.stroke();
        } else if (searching && searchMatches.has(node.id)) {
          ctx.globalAlpha = 1;
          ctx.strokeStyle = "rgba(255, 255, 255, 0.7)";
          ctx.lineWidth = 1.5 / view.k;
          ctx.beginPath();
          ctx.arc(node.x, node.y, node.r + 3 / view.k, 0, Math.PI * 2);
          ctx.stroke();
        }
      }

      // Labels are drawn in screen space, after the transform is cleared: text
      // must not scale with the zoom, and overlap has to be measured in pixels.
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.font = '11px Inter, system-ui, sans-serif';
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillStyle = "#e6e7ee";

      const priority = (node: (typeof sim.nodes)[number]) => {
        if (node.id === focusId || node.id === selectedRef.current) return 1e9;
        if (neighbours?.has(node.id) || searchMatches.has(node.id)) return 1e6 + node.degree;
        return node.degree;
      };
      const candidates = sim.nodes
        .filter(
          (node) =>
            node.id === focusId ||
            node.id === selectedRef.current ||
            !!neighbours?.has(node.id) ||
            searchMatches.has(node.id) ||
            view.k >= LABEL_ALL_ZOOM ||
            node.degree >= LABEL_DEGREE,
        )
        .sort((a, b) => priority(b) - priority(a));

      // Greedy placement, most important label first: a label that would land
      // on one already drawn is dropped rather than rendered illegibly.
      const placed: { x: number; y: number; w: number }[] = [];
      const LABEL_H = 14;
      for (const node of candidates) {
        const sx = width / 2 + view.x + node.x * view.k;
        const sy = height / 2 + view.y + (node.y + node.r) * view.k + 3;
        if (sx < 0 || sx > width || sy < 0 || sy > height - LABEL_H) continue;
        const w = ctx.measureText(node.id).width;
        const left = sx - w / 2;
        const clash = placed.some(
          (r) => left < r.x + r.w + 4 && left + w + 4 > r.x && Math.abs(sy - r.y) < LABEL_H,
        );
        if (clash) continue;
        placed.push({ x: left, y: sy, w });
        const dimmed = !lit(node.id) || (searching && !searchMatches.has(node.id));
        ctx.globalAlpha = dimmed ? 0.2 : 0.92;
        ctx.fillText(node.id, sx, sy);
      }

      // Relation names on the focused node's edges. They sit out near the far
      // end rather than at the midpoint: on a hub like "Python" every midpoint
      // lands in the same place and the labels become a smudge.
      if (focusId && view.k > RELATION_LABEL_ZOOM) {
        ctx.font = '9px "IBM Plex Mono", monospace';
        ctx.fillStyle = "rgba(198, 204, 235, 0.85)";
        ctx.globalAlpha = 1;
        for (const link of sim.links) {
          const atSource = link.source.id === focusId;
          if (!atSource && link.target.id !== focusId) continue;
          const origin: SimNode = atSource ? link.source : link.target;
          const other: SimNode = atSource ? link.target : link.source;
          const gx = origin.x + (other.x - origin.x) * RELATION_LABEL_ALONG;
          const gy = origin.y + (other.y - origin.y) * RELATION_LABEL_ALONG;
          const sx = width / 2 + view.x + gx * view.k;
          const sy = height / 2 + view.y + gy * view.k;
          if (sx < 0 || sx > width || sy < 0 || sy > height - LABEL_H) continue;
          const w = ctx.measureText(link.relation).width;
          const left = sx - w / 2;
          const clash = placed.some(
            (r) => left < r.x + r.w + 4 && left + w + 4 > r.x && Math.abs(sy - r.y) < LABEL_H,
          );
          if (clash) continue;
          placed.push({ x: left, y: sy, w });
          ctx.fillText(link.relation, sx, sy);
        }
      }

      ctx.globalAlpha = 1;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
    };

    // Ticks the layout while it settles, then repaints only when something
    // changed — an idle graph costs nothing.
    const loop = () => {
      const moving = sim.tick();
      if (!moving && !settledOnce) {
        // The opening fit was measured against the starting spiral; now that
        // the layout has come to rest, frame what it actually became.
        settledOnce = true;
        if (!viewOwnedRef.current) fit();
      }
      if (moving || dirtyRef.current) {
        draw();
        dirtyRef.current = false;
      }
      if (moving) positionsRef.current = sim.positions();
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [nodes, edges, fit]);

  useEffect(() => {
    if (fitToken === 0) return;
    viewOwnedRef.current = false;
    fit();
    simRef.current?.reheat(0.35);
  }, [fitToken, fit]);

  // Centre on the selection when it was set from outside the canvas — the
  // search results, the detail panel, or an entity picked out of an answer.
  const cameFromCanvas = useRef<string | null>(selected);
  useEffect(() => {
    if (!selected || selected === cameFromCanvas.current) return;
    cameFromCanvas.current = selected;
    const node = simRef.current?.get(selected);
    if (!node) return;
    const view = viewRef.current;
    viewRef.current = { ...view, x: -node.x * view.k, y: -node.y * view.k };
    dirtyRef.current = true;
  }, [selected]);

  // ---------- pointer interaction ----------

  const drag = useRef<{
    pointerId: number;
    node: SimNode | null;
    startX: number;
    startY: number;
    moved: boolean;
    originX: number;
    originY: number;
  } | null>(null);

  const setHover = useCallback((node: SimNode | null) => {
    if (node?.id === hoveredRef.current) return;
    hoveredRef.current = node?.id ?? null;
    dirtyRef.current = true;
    setHovered(node);
  }, []);

  const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const sim = simRef.current;
    if (!sim) return;
    const { x, y } = toGraph(e.clientX, e.clientY);
    const node = sim.nodeAt(x, y);
    if (node) node.pinned = true;
    drag.current = {
      pointerId: e.pointerId,
      node,
      startX: e.clientX,
      startY: e.clientY,
      moved: false,
      originX: viewRef.current.x,
      originY: viewRef.current.y,
    };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const sim = simRef.current;
    if (!sim) return;
    const state = drag.current;
    if (!state) {
      const { x, y } = toGraph(e.clientX, e.clientY);
      setHover(sim.nodeAt(x, y));
      return;
    }
    const dx = e.clientX - state.startX;
    const dy = e.clientY - state.startY;
    if (!state.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD_PX) return;
    state.moved = true;
    if (state.node) {
      const { x, y } = toGraph(e.clientX, e.clientY);
      state.node.x = x;
      state.node.y = y;
      sim.reheat(0.25);
    } else {
      viewOwnedRef.current = true;
      viewRef.current = { ...viewRef.current, x: state.originX + dx, y: state.originY + dy };
    }
    dirtyRef.current = true;
  };

  const endDrag = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const state = drag.current;
    if (!state) return;
    drag.current = null;
    if (state.node) state.node.pinned = false;
    if (e.currentTarget.hasPointerCapture(state.pointerId)) {
      e.currentTarget.releasePointerCapture(state.pointerId);
    }
    // A drag is a gesture, not a click — only a still pointer changes selection.
    if (!state.moved) {
      const id = state.node?.id ?? null;
      // Selecting from the canvas must not also recentre the view: the node is
      // already under the pointer.
      cameFromCanvas.current = id;
      onSelect(id);
    }
  };

  const onWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const view = viewRef.current;
    const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, view.k * Math.exp(-e.deltaY * 0.0015)));
    // Keep the point under the cursor fixed while the scale changes.
    const px = e.clientX - rect.left - rect.width / 2;
    const py = e.clientY - rect.top - rect.height / 2;
    const ratio = k / view.k;
    viewOwnedRef.current = true;
    viewRef.current = { k, x: px - (px - view.x) * ratio, y: py - (py - view.y) * ratio };
    dirtyRef.current = true;
  };

  return (
    <div className="graph-canvas-wrap" ref={wrapRef}>
      <canvas
        ref={canvasRef}
        className={hovered ? "graph-canvas over-node" : "graph-canvas"}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onPointerLeave={() => setHover(null)}
        onWheel={onWheel}
      />
      {hovered && (
        <div className="graph-hint">
          <span className="dot" style={{ background: typeColor(hovered.type) }} />
          <strong>{hovered.id}</strong>
          <span>
            {hovered.degree} connection{hovered.degree === 1 ? "" : "s"}
          </span>
        </div>
      )}
    </div>
  );
}
