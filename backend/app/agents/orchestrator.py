"""LangGraph Orchestrator.

START -> classify -> [people | skill | team | general] -> synthesize -> END
"""

import json
from functools import partial

from langgraph.graph import END, START, StateGraph

from app.agents import people_agent, skill_agent, team_agent
from app.agents.state import AgentState, QueryAnalysis
from app.graph.model import KnowledgeGraph
from app.llm.provider import LLMProvider

CLASSIFY_SYSTEM = """\
You are the orchestrator of TalentGraph, a workforce knowledge-graph assistant.
Classify the user's query and extract the entities it mentions.

Intents:
- PEOPLE_LOOKUP: find people by skills/technologies/domains, or ask what a person knows
- SKILL_DISCOVERY: explore which skills/technologies exist or who shares them
- RELATIONSHIP_EXPLORATION: how entities are connected (e.g. "How is Alice connected to NLP?")
- PROJECT_MATCHING: who is suitable for a project with given requirements
- TEAM_COMPOSITION: assemble a team for given requirements
- SKILL_GAP: what capabilities are missing for a project/team
- GENERAL: greetings, meta questions, or anything else

Rules:
- Use the conversation history to resolve references: rewrite the query as a fully
  self-contained question in `resolved_query` (e.g. "which of them" -> the actual
  people from the previous answer).
- `capabilities` are concrete skills/technologies (Python, AWS, React, NLP...).
- Only list names in `people` when the query itself refers to those specific people
  (by name or by pronoun reference). Never copy people from history into `people`
  for a query that searches by capability.
- Comparison questions about specific people ("why Alice over David?") are
  PEOPLE_LOOKUP with both people listed.
"""

SYNTHESIZE_SYSTEM = """\
You are TalentGraph, a workforce intelligence assistant. Answer the user's question
using ONLY the graph evidence provided. Rules:
- Every claim must be supported by the provided agent results and evidence; if the
  graph does not contain the answer, say so plainly rather than guessing.
- Be concise and direct. Name the people/skills/projects involved and why.
- When recommending or comparing people, explain the evidence (skills held,
  projects worked on, gaps).
- Do not mention internal machinery (agents, JSON, graph traversal).

Format the answer in GitHub-flavored Markdown so it can be skimmed:
- ALWAYS start with a blockquote of one or two sentences giving the key takeaway:
  `> **Key takeaway:** ...`. A reader who stops there must still get the answer.
- After the takeaway, organize the rest under short `###` section headings
  (e.g. `### Who fits`, `### Gaps`, `### Recommendation`). Skip headings only for
  trivially short answers.
- Use bullet points instead of long paragraphs; bold the names of people, skills,
  and projects on first mention.
- Use a Markdown table when comparing people or mapping people/roles to
  capabilities (e.g. columns: Person | Covers | Evidence). Keep cells short and
  put explanations in surrounding text, not in cells.
- Keep the whole answer tight: no filler, no restating the question.
"""


def build_orchestrator(kg: KnowledgeGraph, provider: LLMProvider):
    def classify(state: AgentState) -> dict:
        history_text = _render_history(state.get("history", []))
        analysis = provider.parse(
            system=CLASSIFY_SYSTEM,
            user=f"Conversation history:\n{history_text}\n\nUser query: {state['user_query']}",
            schema=QueryAnalysis,
        )
        return {"intent": analysis.intent, "analysis": analysis.model_dump()}

    def route(state: AgentState) -> str:
        return {
            "PEOPLE_LOOKUP": "people",
            "SKILL_DISCOVERY": "people",
            "RELATIONSHIP_EXPLORATION": "skill",
            "PROJECT_MATCHING": "team",
            "TEAM_COMPOSITION": "team",
            "SKILL_GAP": "team",
        }.get(state["intent"], "general")

    def general(state: AgentState) -> dict:
        people = kg.nodes_of_type("person")
        overview = {
            "people": people,
            "skills": len(kg.nodes_of_type("skill")),
            "technologies": len(kg.nodes_of_type("technology")),
            "projects": kg.nodes_of_type("project"),
            "domains": kg.nodes_of_type("domain"),
        }
        return {"agent_results": {**state.get("agent_results", {}), "overview": overview}}

    def synthesize(state: AgentState) -> dict:
        payload = {
            "question": state["analysis"]["resolved_query"],
            "intent": state["intent"],
            "agent_results": state.get("agent_results", {}),
            "evidence": [e["detail"] for e in state.get("evidence", [])],
        }
        answer = provider.complete(
            system=SYNTHESIZE_SYSTEM,
            user=json.dumps(payload, indent=2, ensure_ascii=False),
        )
        return {"final_answer": answer}

    graph = StateGraph(AgentState)
    graph.add_node("classify", classify)
    graph.add_node("people", partial(people_agent.run, kg=kg))
    graph.add_node("skill", partial(skill_agent.run, kg=kg))
    graph.add_node("team", partial(team_agent.run, kg=kg))
    graph.add_node("general", general)
    graph.add_node("synthesize", synthesize)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        route,
        {"people": "people", "skill": "skill", "team": "team", "general": "general"},
    )
    for node in ("people", "skill", "team", "general"):
        graph.add_edge(node, "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()


def _render_history(history) -> str:
    if not history:
        return "(none)"
    lines = []
    for turn in history[-5:]:
        lines.append(f"User: {turn['user']}")
        lines.append(f"Assistant: {turn['answer']}")
        if turn.get("entities"):
            lines.append(f"(entities involved: {', '.join(turn['entities'])})")
    return "\n".join(lines)
