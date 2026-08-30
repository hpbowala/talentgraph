"""Serialisable view of the knowledge graph, for the frontend graph explorer.

The chat path only ever needs the slice of the graph an answer touches; the
explorer needs the whole thing at once. This module flattens the in-memory
MultiDiGraph into plain nodes and edges — the same relations the agents
traverse, so what the explorer draws is literally what the answers are grounded
in.
"""

from app.graph.model import KnowledgeGraph
from app.models import GraphEdge, GraphNode, GraphSnapshot


def build_snapshot(kg: KnowledgeGraph, indexed_at: str | None = None) -> GraphSnapshot:
    """Flatten the graph into nodes + edges.

    Parallel edges carrying the same relation are collapsed (the vault can state
    a relation from both ends), keeping the first evidence quote we see.
    """
    seen: set[tuple[str, str, str]] = set()
    edges: list[GraphEdge] = []
    for source, target, data in kg.g.edges(data=True):
        key = (source, target, data["relation"])
        if key in seen:
            continue
        seen.add(key)
        edges.append(
            GraphEdge(
                source=source,
                target=target,
                relation=data["relation"],
                evidence=data.get("evidence") or None,
            )
        )

    # Degree counts the edges the explorer actually draws, not the parallel
    # ones collapsed above, so the node sizes match what is on screen.
    degrees: dict[str, int] = {}
    for edge in edges:
        degrees[edge.source] = degrees.get(edge.source, 0) + 1
        degrees[edge.target] = degrees.get(edge.target, 0) + 1

    nodes = [
        GraphNode(
            id=name,
            type=data.get("type", "unknown"),
            degree=degrees.get(name, 0),
            role=data.get("role") or None,
            path=data.get("path") or None,
        )
        for name, data in kg.g.nodes(data=True)
    ]
    nodes.sort(key=lambda n: (n.type, n.id.lower()))

    counts: dict[str, int] = {}
    for node in nodes:
        counts[node.type] = counts.get(node.type, 0) + 1

    return GraphSnapshot(nodes=nodes, edges=edges, counts=counts, indexed_at=indexed_at)
