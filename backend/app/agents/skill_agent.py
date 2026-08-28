"""Skill/Graph Agent: relationships between skills, technologies, projects,
domains and people."""

from app.graph.model import KnowledgeGraph
from app.graph.retriever import find_paths, related_entities
from app.state_utils import evidence_ref


def run(state: dict, kg: KnowledgeGraph) -> dict:
    analysis = state["analysis"]
    mentioned = [*analysis["people"], *analysis["capabilities"], *analysis["domains"]]
    resolved = [r for r in (kg.resolve(name) for name in mentioned) if r]

    results: dict = {}
    evidence: list[dict] = []
    paths: list[str] = []

    if len(resolved) >= 2:
        for i, a in enumerate(resolved):
            for b in resolved[i + 1 :]:
                found = find_paths(kg, a, b)
                if found:
                    results.setdefault("paths", {})[f"{a} <-> {b}"] = found
                    paths.extend(found)
                    for p in found:
                        evidence.append(evidence_ref("path", p, kg.node_path(a)))

    for entity in resolved:
        connections = related_entities(kg, entity)
        results.setdefault("connections", {})[entity] = connections
        for c in connections[:20]:
            arrow = "—" if c["direction"] == "out" else "←"
            evidence.append(
                evidence_ref(
                    "relation",
                    f"{entity} {arrow}{c['relation']}{'→' if c['direction'] == 'out' else '—'} "
                    f"{c['entity']}",
                    kg.node_path(entity),
                )
            )

    if not resolved:
        results["note"] = "No graph entities could be resolved from the query."

    return {
        "agent_results": {**state.get("agent_results", {}), "skill_agent": results},
        "evidence": [*state.get("evidence", []), *evidence],
        "graph_paths": [*state.get("graph_paths", []), *paths],
        "retrieved_nodes": [*state.get("retrieved_nodes", []), *resolved],
    }
