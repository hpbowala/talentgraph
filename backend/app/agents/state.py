"""LangGraph conversational state."""

from typing import Literal, TypedDict

from pydantic import BaseModel, Field

Intent = Literal[
    "PEOPLE_LOOKUP",
    "SKILL_DISCOVERY",
    "RELATIONSHIP_EXPLORATION",
    "PROJECT_MATCHING",
    "TEAM_COMPOSITION",
    "SKILL_GAP",
    "GENERAL",
]


class QueryAnalysis(BaseModel):
    """Structured output of the classify node."""

    intent: Intent
    resolved_query: str = Field(
        description=(
            "The user query rewritten as a fully self-contained question, with any "
            "pronouns or references like 'them'/'that project' expanded using the "
            "conversation history"
        )
    )
    capabilities: list[str] = Field(
        default_factory=list,
        description="Skills or technologies mentioned or required (e.g. Python, AWS, React)",
    )
    people: list[str] = Field(
        default_factory=list, description="Person names mentioned in the query"
    )
    domains: list[str] = Field(
        default_factory=list, description="Domains mentioned (e.g. Artificial Intelligence)"
    )
    team_size: int | None = Field(
        default=None, description="Requested team size, if the query asks to build a team"
    )


class HistoryTurn(TypedDict):
    user: str
    answer: str
    entities: list[str]


class AgentState(TypedDict, total=False):
    conversation_id: str
    user_query: str
    history: list[HistoryTurn]
    intent: str
    analysis: dict  # QueryAnalysis dump
    retrieved_nodes: list[str]
    graph_paths: list[str]
    agent_results: dict
    evidence: list[dict]  # EvidenceRef dumps
    final_answer: str
