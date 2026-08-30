"""Serialisable view of the knowledge graph, for the frontend graph explorer.

Flattens the in-memory MultiDiGraph the agents traverse into plain nodes and
edges — the chat path only needs the slice an answer touches, the explorer
needs the whole thing at once.
"""

from app.graph.model import KnowledgeGraph
from app.models import GraphEdge, GraphNode, GraphSnapshot


def build_snapshot(kg: KnowledgeGraph, indexed_at: str | None = None) -> GraphSnapshot:
    """Flatten the graph into nodes + edges.

    Parallel edges with the same relation are collapsed, keeping the first
    evidence quote.
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
