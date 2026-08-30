"""Pydantic schemas shared across ingestion, agents and the API."""

from pydantic import BaseModel, Field


class EvidencedItem(BaseModel):
    """An extracted entity name plus the CV sentence that supports it."""

    name: str = Field(description="The skill/technology name exactly as written in the CV")
    evidence: str = Field(description="A short verbatim quote from the CV supporting this item")


class ProjectEntry(BaseModel):
    name: str = Field(description="Project name as written in the CV")
    description: str = Field(description="One-sentence summary of the project")
    technologies: list[str] = Field(description="Technologies used in this project")
    domains: list[str] = Field(default_factory=list, description="Domains this project belongs to")
    evidence: str = Field(description="Verbatim CV quote mentioning this project")


class ExperienceEntry(BaseModel):
    role: str
    organization: str
    start_year: int | None = None
    end_year: int | None = Field(default=None, description="None if this is the current role")
    summary: str = Field(description="One-sentence summary of what the person did")


class EducationEntry(BaseModel):
    qualification: str = Field(description="Degree or qualification name")
    institution: str
    year: int | None = None


class CVProfile(BaseModel):
    """Structured representation of a single CV."""

    person_name: str
    headline: str = Field(description="Current role/title, e.g. 'Senior AI Engineer'")
    summary: str = Field(description="One or two sentence professional summary")
    skills: list[EvidencedItem]
    technologies: list[EvidencedItem]
    domains: list[str]
    projects: list[ProjectEntry]
    experience: list[ExperienceEntry]
    education: list[EducationEntry]


class EvidenceRef(BaseModel):
    """A piece of graph evidence attached to an answer, so it can be explained."""

    kind: str = Field(description="e.g. 'relation', 'path', 'note'")
    detail: str = Field(
        description="Human-readable evidence, e.g. 'Alice Perera —HAS_SKILL→ Python'"
    )
    source: str | None = Field(default=None, description="Vault note path backing this evidence")


class ChatResponse(BaseModel):
    answer: str
    intent: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    conversation_id: str


class GraphNode(BaseModel):
    """One vault note as a point in the graph explorer."""

    id: str = Field(description="Note name, which is also the node identity")
    type: str = Field(description="person | skill | technology | project | domain | education")
    degree: int = Field(description="Number of connections drawn for this node")
    role: str | None = Field(default=None, description="Headline, for person nodes")
    path: str | None = Field(default=None, description="Vault note path backing this node")


class GraphEdge(BaseModel):
    """A typed connection between two notes."""

    source: str
    target: str
    relation: str = Field(description="e.g. HAS_SKILL, USES, WORKED_ON")
    evidence: str | None = Field(default=None, description="CV quote the relation came from")


class GraphSnapshot(BaseModel):
    """The whole knowledge graph, as the explorer draws it."""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict, description="Node count per type")
    indexed_at: str | None = Field(default=None, description="Stamp of the live index build")


class CVSummary(BaseModel):
    """One document in the managed CV corpus."""

    filename: str
    size_bytes: int
    uploaded_at: str
    person: str | None = Field(
        default=None, description="Person the last index build extracted from this CV"
    )


class CVLibrary(BaseModel):
    """The CV corpus behind the graph, returned after every library change."""

    cvs: list[CVSummary] = Field(default_factory=list)
    indexed_at: str | None = Field(default=None, description="Stamp of the live index build")
    note_count: int | None = Field(
        default=None, description="Notes written by the rebuild this response reports on"
    )


class ConversationSummary(BaseModel):
    """Sidebar thread-list entry."""

    conversation_id: str
    title: str
    updated_at: str


class ConversationTurn(BaseModel):
    """One stored user/assistant exchange."""

    user: str
    answer: str
    intent: str = "GENERAL"
    evidence: list[EvidenceRef] = Field(default_factory=list)
    ts: str | None = None


class ConversationDetail(BaseModel):
    conversation_id: str
    title: str
    turns: list[ConversationTurn]
