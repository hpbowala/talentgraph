"""People Agent: person-centric lookup and capability discovery."""

from app.graph.model import KnowledgeGraph
from app.graph.retriever import find_people, get_person_profile
from app.state_utils import evidence_ref


def run(state: dict, kg: KnowledgeGraph) -> dict:
    analysis = state["analysis"]
    capabilities = analysis["capabilities"]
    domains = analysis["domains"]
    people = [p for p in (kg.resolve(name) for name in analysis["people"]) if p]

    results: dict = {}
    evidence: list[dict] = []
    retrieved: list[str] = []

    if capabilities or domains:
        matches = find_people(kg, capabilities=capabilities, domains=domains, match="all")
        partial = []
        if not matches or len(capabilities) + len(domains) > 1:
            all_matches = find_people(kg, capabilities=capabilities, domains=domains, match="any")
            partial = [m for m in all_matches if m.person not in {x.person for x in matches}]
        results["full_matches"] = [
            {"person": m.person, "matched": m.matched, "missing": m.missing} for m in matches
        ]
        results["partial_matches"] = [
            {"person": m.person, "matched": m.matched, "missing": m.missing} for m in partial
        ]
        for m in [*matches, *partial]:
            retrieved.append(m.person)
            for detail in m.matched.values():
                evidence.append(evidence_ref("relation", detail, kg.node_path(m.person)))

    for person in people:
        profile = get_person_profile(kg, person)
        results.setdefault("profiles", {})[person] = profile
        retrieved.append(person)
        for relation, targets in profile.items():
            for t in targets:
                evidence.append(
                    evidence_ref(
                        "relation",
                        f"{person} —{relation}→ {t['target']}",
                        kg.node_path(person),
                    )
                )

    return {
        "agent_results": {**state.get("agent_results", {}), "people_agent": results},
        "evidence": [*state.get("evidence", []), *evidence],
        "retrieved_nodes": [*state.get("retrieved_nodes", []), *retrieved],
    }
