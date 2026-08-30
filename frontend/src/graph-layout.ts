/** Force-directed layout for the graph explorer.
 *
 *  Written by hand rather than pulled from d3-force: the whole simulation is
 *  three forces over a few hundred nodes, and the explorer needs to drive the
 *  ticks itself so it can render into a canvas on the same frame.
 */

import type { GraphEdge, GraphNode } from "./types";

export interface SimNode {
  id: string;
  type: string;
  degree: number;
  role: string | null;
  /** Radius in graph units — derived from degree, so hubs read as hubs. */
  r: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  /** Set while the pointer is dragging this node; the forces leave it alone. */
  pinned: boolean;
}

export interface SimLink {
  source: SimNode;
  target: SimNode;
  relation: string;
  evidence: string | null;
}

/** Concentric bands for the starting positions: people in the middle, the
 *  vocabulary they connect through further out. A good opening arrangement is
 *  worth more than extra iterations. */
const TYPE_RANK: Record<string, number> = {
  person: 0,
  project: 1,
  domain: 2,
  skill: 3,
  technology: 4,
  education: 5,
  unknown: 6,
};

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

/* Force constants follow d3-force's formulation, which is what keeps the
   simulation stable: repulsion falls off as 1/d rather than 1/d², and every
   force is scaled by alpha so the whole system cools predictably. Tuned
   against the sample vault, where ~300 notes settle in roughly 250 ticks. */
const REPULSION = 42;
const REPULSION_PER_RADIUS = 4;
const LINK_DISTANCE = 34;
const LINK_STRENGTH = 0.7;
const CENTER_STRENGTH = 0.05;
const VELOCITY_DECAY = 0.6;
const ALPHA_DECAY = 0.0228;
const SEEDED_ALPHA = 0.45;
const ALPHA_MIN = 0.004;
/* A speed limit per tick. The forces above settle on their own without it —
   it exists so a pathological graph cannot blow the layout out to infinity,
   and it keeps the opening frames from flying apart before they converge. */
const MAX_SPEED = 40;

export function nodeRadius(degree: number): number {
  return Math.min(4 + Math.sqrt(degree) * 1.7, 20);
}

export class Simulation {
  readonly nodes: SimNode[];
  readonly links: SimLink[];
  private byId: Map<string, SimNode>;
  /** Per-link spring weighting, indexed alongside `links`. */
  private springs: { strength: number; bias: number }[] = [];
  private alpha: number;

  constructor(nodes: GraphNode[], edges: GraphEdge[], seed?: Map<string, { x: number; y: number }>) {
    // Placement order, not render order: sorting by band keeps the spiral below
    // laying each type out in its own ring.
    const ordered = [...nodes].sort(
      (a, b) => (TYPE_RANK[a.type] ?? 9) - (TYPE_RANK[b.type] ?? 9) || b.degree - a.degree,
    );

    this.nodes = ordered.map((node, i) => {
      const placed = seed?.get(node.id);
      const angle = i * GOLDEN_ANGLE;
      const radius = Math.sqrt(i + 1) * 26;
      return {
        id: node.id,
        type: node.type,
        degree: node.degree,
        role: node.role ?? null,
        r: nodeRadius(node.degree),
        x: placed?.x ?? Math.cos(angle) * radius,
        y: placed?.y ?? Math.sin(angle) * radius,
        vx: 0,
        vy: 0,
        pinned: false,
      };
    });

    // A rebuild seeded with the previous positions starts close to its answer,
    // so it needs a nudge rather than a full reheat — that is what makes
    // toggling a type filter feel immediate instead of scattering the graph.
    this.alpha = seed && seed.size > 0 ? SEEDED_ALPHA : 1;

    this.byId = new Map(this.nodes.map((n) => [n.id, n]));
    this.links = edges.flatMap((edge) => {
      const source = this.byId.get(edge.source);
      const target = this.byId.get(edge.target);
      // Edges to filtered-out nodes simply do not exist in this simulation.
      if (!source || !target || source === target) return [];
      return [{ source, target, relation: edge.relation, evidence: edge.evidence ?? null }];
    });

    // Weight each spring by the degree of the nodes it joins, counted within
    // the visible graph. A leaf hanging off a hub is then pulled towards the
    // hub rather than dragging it around — without this, "Python" with its 95
    // connections would be yanked in 95 directions at once.
    const linkCount = new Map<SimNode, number>();
    for (const link of this.links) {
      linkCount.set(link.source, (linkCount.get(link.source) ?? 0) + 1);
      linkCount.set(link.target, (linkCount.get(link.target) ?? 0) + 1);
    }
    this.springs = this.links.map((link) => {
      const source = linkCount.get(link.source)!;
      const target = linkCount.get(link.target)!;
      return {
        strength: LINK_STRENGTH / Math.min(source, target),
        bias: source / (source + target),
      };
    });
  }

  get(id: string): SimNode | undefined {
    return this.byId.get(id);
  }

  positions(): Map<string, { x: number; y: number }> {
    return new Map(this.nodes.map((n) => [n.id, { x: n.x, y: n.y }]));
  }

  get settled(): boolean {
    return this.alpha < ALPHA_MIN;
  }

  reheat(alpha = 0.6): void {
    this.alpha = Math.max(this.alpha, alpha);
  }

  /** Advance one frame. Returns false once the layout has come to rest. */
  tick(): boolean {
    if (this.settled) return false;
    const { nodes, links, springs, alpha } = this;

    // Repulsion — every pair, which is affordable at this scale (a few hundred
    // nodes) and avoids the failure mode of a cutoff radius: disconnected
    // clusters drifting apart forever.
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let d2 = dx * dx + dy * dy;
        if (d2 < 1) {
          // Coincident nodes have no direction to separate along; nudge them
          // apart deterministically by index rather than at random, so the
          // layout is reproducible.
          dx = ((i % 7) - 3) * 0.3 + 0.1;
          dy = ((j % 7) - 3) * 0.3 + 0.1;
          d2 = dx * dx + dy * dy;
        }
        const w = ((REPULSION + (a.r + b.r) * REPULSION_PER_RADIUS) * alpha) / d2;
        const fx = dx * w;
        const fy = dy * w;
        a.vx -= fx;
        a.vy -= fy;
        b.vx += fx;
        b.vy += fy;
      }
    }

    // Springs along the edges.
    for (let i = 0; i < links.length; i++) {
      const { source, target } = links[i];
      const spring = springs[i];
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 1;
      const rest = LINK_DISTANCE + source.r + target.r;
      const pull = ((d - rest) / d) * alpha * spring.strength;
      const fx = dx * pull;
      const fy = dy * pull;
      target.vx -= fx * spring.bias;
      target.vy -= fy * spring.bias;
      source.vx += fx * (1 - spring.bias);
      source.vy += fy * (1 - spring.bias);
    }

    // Gravity towards the origin, so the graph stays framed.
    for (const node of nodes) {
      node.vx -= node.x * CENTER_STRENGTH * alpha;
      node.vy -= node.y * CENTER_STRENGTH * alpha;
      if (node.pinned) {
        node.vx = 0;
        node.vy = 0;
        continue;
      }
      const speed = Math.hypot(node.vx, node.vy);
      if (speed > MAX_SPEED) {
        const scale = MAX_SPEED / speed;
        node.vx *= scale;
        node.vy *= scale;
      }
      node.x += node.vx *= VELOCITY_DECAY;
      node.y += node.vy *= VELOCITY_DECAY;
    }

    this.alpha += (0 - this.alpha) * ALPHA_DECAY;
    return true;
  }

  /** Bounding box of the laid-out nodes, for framing the view.
   *
   *  `trim` discards that fraction of nodes from each edge before measuring.
   *  A vault always has a few unconnected fragments that drift far out, and
   *  framing to the literal extremes would shrink the interesting middle to
   *  nothing to accommodate them.
   */
  bounds(trim = 0): { minX: number; minY: number; maxX: number; maxY: number } {
    if (this.nodes.length === 0) return { minX: -1, minY: -1, maxX: 1, maxY: 1 };
    const pad = Math.max(...this.nodes.map((n) => n.r));
    const xs = this.nodes.map((n) => n.x).sort((a, b) => a - b);
    const ys = this.nodes.map((n) => n.y).sort((a, b) => a - b);
    const lo = Math.min(Math.floor(xs.length * trim), xs.length - 1);
    const hi = Math.max(xs.length - 1 - lo, lo);
    return {
      minX: xs[lo] - pad,
      maxX: xs[hi] + pad,
      minY: ys[lo] - pad,
      maxY: ys[hi] + pad,
    };
  }

  /** Node under a point in graph space, largest hit first. */
  nodeAt(x: number, y: number, slack = 4): SimNode | null {
    let found: SimNode | null = null;
    for (const node of this.nodes) {
      const dx = node.x - x;
      const dy = node.y - y;
      const reach = node.r + slack;
      if (dx * dx + dy * dy <= reach * reach && (!found || node.r > found.r)) {
        found = node;
      }
    }
    return found;
  }
}
