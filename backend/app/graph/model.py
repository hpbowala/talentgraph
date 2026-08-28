"""In-memory knowledge graph over the parsed vault."""

import difflib
from pathlib import Path

import networkx as nx

from app.graph.parser import ParsedEdge, ParsedNote, parse_vault


class KnowledgeGraph:
    def __init__(self, notes: list[ParsedNote], edges: list[ParsedEdge]):
        self.g = nx.MultiDiGraph()
        self._alias_index: dict[str, str] = {}
        for note in notes:
            self.g.add_node(note.name, type=note.type, path=note.path)
            self._alias_index[note.name.lower()] = note.name
            for alias in note.aliases:
                self._alias_index[alias.lower()] = note.name
        for edge in edges:
            # Wikilink targets sanitize "/" to "-"; resolve back to a known node if possible.
            target = self._alias_index.get(edge.target.lower(), edge.target)
            if target not in self.g:
                self.g.add_node(target, type="unknown", path="")
            self.g.add_edge(
                edge.source,
                target,
                relation=edge.relation,
                evidence=edge.evidence,
                source_note=edge.source_note,
            )
        self._undirected = self.g.to_undirected(as_view=False)

    @classmethod
    def from_vault(cls, vault_dir: Path) -> "KnowledgeGraph":
        notes, edges = parse_vault(vault_dir)
        return cls(notes, edges)

    # lookup

    def resolve(self, name: str) -> str | None:
        """Resolve a user-supplied name to a node (exact, alias, then fuzzy)."""
        key = name.strip().lower()
        if key in self._alias_index:
            return self._alias_index[key]
        # First-name match for people ("alice" -> "Alice Perera").
        candidates = [
            node
            for node, data in self.g.nodes(data=True)
            if data.get("type") == "person" and node.lower().split()[0] == key
        ]
        if len(candidates) == 1:
            return candidates[0]
        close = difflib.get_close_matches(key, list(self._alias_index), n=1, cutoff=0.75)
        return self._alias_index[close[0]] if close else None

    def node_type(self, name: str) -> str:
        return self.g.nodes[name].get("type", "unknown") if name in self.g else "unknown"

    def node_path(self, name: str) -> str:
        return self.g.nodes[name].get("path", "") if name in self.g else ""

    def nodes_of_type(self, node_type: str) -> list[str]:
        return sorted(n for n, d in self.g.nodes(data=True) if d.get("type") == node_type)

    # traversal

    def out_edges(self, name: str, relation: str | None = None):
        """Outgoing (source, target, data) triples, optionally filtered by relation."""
        if name not in self.g:
            return []
        return [
            (u, v, d)
            for u, v, d in self.g.out_edges(name, data=True)
            if relation is None or d["relation"] == relation
        ]

    def in_edges(self, name: str, relation: str | None = None):
        if name not in self.g:
            return []
        return [
            (u, v, d)
            for u, v, d in self.g.in_edges(name, data=True)
            if relation is None or d["relation"] == relation
        ]

    def paths(self, a: str, b: str, max_hops: int = 4, limit: int = 5) -> list[list[str]]:
        """Shortest undirected paths between two nodes, used as graph-path evidence."""
        if a not in self.g or b not in self.g:
            return []
        try:
            gen = nx.all_shortest_paths(self._undirected, a, b)
            paths = []
            for path in gen:
                if len(path) - 1 > max_hops:
                    break
                paths.append(path)
                if len(paths) >= limit:
                    break
            return paths
        except nx.NetworkXNoPath:
            return []

    def edge_between(self, a: str, b: str) -> tuple[str, bool] | None:
        """Relation label between adjacent nodes, trying both directions.

        Returns (relation, forward) or None.
        """
        data = self.g.get_edge_data(a, b)
        if data:
            return next(iter(data.values()))["relation"], True
        data = self.g.get_edge_data(b, a)
        if data:
            return next(iter(data.values()))["relation"], False
        return None
