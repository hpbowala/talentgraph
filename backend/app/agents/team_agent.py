"""Team Analysis Agent: candidate matching, team composition and gap analysis.
Greedy set-cover team selection over the capability graph."""

from app.graph.model import KnowledgeGraph
from app.graph.retriever import coverage, find_people
from app.state_utils import evidence_ref

DEFAULT_TEAM_SIZE = 3


def run(state: dict, kg: KnowledgeGraph) -> dict:
    analysis = state["analysis"]
    required = [*analysis["capabilities"], *analysis["domains"]]
    team_size = analysis.get("team_size") or DEFAULT_TEAM_SIZE

    candidates = find_people(
        kg, capabilities=analysis["capabilities"], domains=analysis["domains"], match="any"
    )

    results: dict = {
        "required_capabilities": required,
        "candidates": [
            {
                "person": m.person,
                "score": round(m.score, 2),
                "matched": m.matched,
                "missing": m.missing,
            }
            for m in candidates
        ],
    }
    evidence = [
        evidence_ref("relation", detail, kg.node_path(m.person))
        for m in candidates
        for detail in m.matched.values()
    ]

    if state.get("intent") in ("TEAM_COMPOSITION", "SKILL_GAP") and candidates:
        team = _greedy_team(candidates, team_size)
        team_coverage = coverage(kg, required, team)
        results["proposed_team"] = team
        results["coverage"] = team_coverage
        if team_coverage["gaps"]:
            evidence.append(
                evidence_ref(
                    "gap",
                    "No one in the proposed team covers: " + ", ".join(team_coverage["gaps"]),
                )
            )

    return {
        "agent_results": {**state.get("agent_results", {}), "team_agent": results},
        "evidence": [*state.get("evidence", []), *evidence],
        "retrieved_nodes": [
            *state.get("retrieved_nodes", []),
            *[m.person for m in candidates],
        ],
    }


def _greedy_team(candidates, team_size: int) -> list[str]:
    """Pick people maximizing newly covered capabilities, then overall score."""
    team: list[str] = []
    covered: set[str] = set()
    pool = list(candidates)
    while pool and len(team) < team_size:
        best = max(pool, key=lambda m: (len(set(m.matched) - covered), m.score))
        team.append(best.person)
        covered |= set(best.matched)
        pool.remove(best)
    return team
