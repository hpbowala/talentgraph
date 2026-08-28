import pytest

from app.graph.model import KnowledgeGraph
from app.ingest.vault_writer import write_vault
from app.models import CVProfile, EducationEntry, EvidencedItem, ExperienceEntry, ProjectEntry


def _item(name: str) -> EvidencedItem:
    return EvidencedItem(name=name, evidence=f"worked with {name}")


@pytest.fixture()
def sample_profiles() -> list[CVProfile]:
    alice = CVProfile(
        person_name="Alice Perera",
        headline="Senior AI Engineer",
        summary="AI engineer focused on NLP.",
        skills=[_item("Python"), _item("AWS"), _item("NLP")],
        technologies=[_item("FastAPI")],
        domains=["Artificial Intelligence"],
        projects=[
            ProjectEntry(
                name="Customer Support AI",
                description="LLM support assistant",
                technologies=["LangChain"],
                domains=["Artificial Intelligence"],
                evidence="Led the Customer Support AI project",
            )
        ],
        experience=[
            ExperienceEntry(
                role="Senior AI Engineer",
                organization="Nexlify",
                start_year=2021,
                summary="Led AI work",
            )
        ],
        education=[
            EducationEntry(
                qualification="MSc in AI", institution="University of Moratuwa", year=2018
            )
        ],
    )
    bob = CVProfile(
        person_name="Bob Silva",
        headline="Backend Engineer",
        summary="Backend engineer.",
        skills=[_item("Python"), _item("AWS")],
        technologies=[_item("Docker")],
        domains=["Backend Development"],
        projects=[
            ProjectEntry(
                name="Payment Gateway",
                description="Payments backend",
                technologies=["FastAPI"],
                domains=["Backend Development"],
                evidence="Built the Payment Gateway",
            )
        ],
        experience=[],
        education=[],
    )
    return [alice, bob]


@pytest.fixture()
def kg(tmp_path, sample_profiles) -> KnowledgeGraph:
    write_vault(
        sample_profiles,
        {"Alice Perera": "alice.pdf", "Bob Silva": "bob.pdf"},
        tmp_path / "vault",
    )
    return KnowledgeGraph.from_vault(tmp_path / "vault")
