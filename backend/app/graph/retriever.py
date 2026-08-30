"""Graph-aware retrieval tools used by the specialist agents.

Each returns plain data plus evidence strings for the synthesis step to cite.
"""

from dataclasses import dataclass, field

from app.graph.model import KnowledgeGraph

CAPABILITY_RELATIONS = ("HAS_SKILL", "USES")


@dataclass
class Match:
    person: str
    matched: dict[str, str] = field(default_factory=dict)  # capability -> evidence string
    missing: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        total = len(self.matched) + len(self.missing)
        return len(self.matched) / total if total else 0.0


def resolve_capabilities(kg: KnowledgeGraph, names: list[str]) -> tuple[list[str], list[str]]:
    """Resolve requested capability names to graph nodes; returns (resolved, unknown)."""
    resolved, unknown = [], []
    for name in names:
        node = kg.resolve(name)
        (resolved if node else unknown).append(node or name)
    return resolved, unknown


def person_has(kg: KnowledgeGraph, person: str, capability: str) -> str | None:
    """Evidence string if the person has the capability (skill/tech edge), else None."""
    for _, target, data in kg.out_edges(person):
        if data["relation"] in CAPABILITY_RELATIONS and target == capability:
            return f"{person} —{data['relation']}→ {capability}"
    return None


def find_people(
    kg: KnowledgeGraph,
    capabilities: list[str] | None = None,
    domains: list[str] | None = None,
    match: str = "all",
) -> list[Match]:
    """People matching required capabilities and/or domains."""
    caps, _ = resolve_capabilities(kg, capabilities or [])
    doms, _ = resolve_capabilities(kg, domains or [])
    results = []
    for person in kg.nodes_of_type("person"):
        m = Match(person=person)
        for cap in caps:
            evidence = person_has(kg, person, cap)
            if evidence:
                m.matched[cap] = evidence
            else:
                m.missing.append(cap)
        for dom in doms:
            hit = any(
                t == dom and d["relation"] == "EXPERIENCE_IN" for _, t, d in kg.out_edges(person)
            )
            if hit:
                m.matched[dom] = f"{person} —EXPERIENCE_IN→ {dom}"
            else:
                m.missing.append(dom)
        if not m.matched:
            continue
        if match == "all" and m.missing:
            continue
        results.append(m)
    return sorted(results, key=lambda m: (-m.score, m.person))


def get_person_profile(kg: KnowledgeGraph, person: str) -> dict[str, list[dict]]:
    """All outgoing relations of a person, grouped by relation type."""
    profile: dict[str, list[dict]] = {}
    for _, target, data in kg.out_edges(person):
        profile.setdefault(data["relation"], []).append(
            {"target": target, "evidence": data.get("evidence", "")}
        )
    return profile


def find_paths(kg: KnowledgeGraph, a: str, b: str, max_hops: int = 4) -> list[str]:
    """Human-readable graph paths between two entities."""
    rendered = []
    for path in kg.paths(a, b, max_hops=max_hops):
        parts = [path[0]]
        for prev, nxt in zip(path, path[1:], strict=False):
            edge = kg.edge_between(prev, nxt)
            label = edge[0] if edge else "RELATED"
            arrow = f"—{label}→" if edge and edge[1] else f"←{label}—"
            parts.append(f" {arrow} {nxt}")
        rendered.append("".join(parts))
    return rendered


def related_entities(kg: KnowledgeGraph, name: str, relation: str | None = None) -> list[dict]:
    """Entities connected to `name` in either direction."""
    results = []
    for _, target, data in kg.out_edges(name, relation):
        results.append(
            {
                "entity": target,
                "relation": data["relation"],
                "direction": "out",
                "type": kg.node_type(target),
            }
        )
    for source, _, data in kg.in_edges(name, relation):
        results.append(
            {
                "entity": source,
                "relation": data["relation"],
                "direction": "in",
                "type": kg.node_type(source),
            }
        )
    return results


def coverage(kg: KnowledgeGraph, required: list[str], people: list[str]) -> dict:
    """Team capability coverage: which requirements the group covers, and gaps."""
    caps, unknown = resolve_capabilities(kg, required)
    covered: dict[str, list[str]] = {}
    for cap in caps:
        holders = [p for p in people if person_has(kg, p, cap)]
        if holders:
            covered[cap] = holders
    gaps = [cap for cap in caps if cap not in covered] + unknown
    return {"covered": covered, "gaps": gaps}
