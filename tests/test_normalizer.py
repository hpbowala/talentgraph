from app.ingest.normalizer import normalize_name, normalize_profile
from app.models import CVProfile, EvidencedItem


def test_alias_table_traps():
    assert normalize_name("Amazon Web Services") == "AWS"
    assert normalize_name("Natural Language Processing") == "NLP"
    assert normalize_name("ReactJS") == "React"
    assert normalize_name("Application Programming Interface design") == "API design"
    assert normalize_name("JS") == "JavaScript"


def test_case_and_whitespace_insensitive():
    assert normalize_name("  amazon   web services ") == "AWS"
    assert normalize_name("reactjs") == "React"


def test_parenthetical_qualifiers_stripped():
    assert normalize_name("Python (expert)") == "Python"
    assert normalize_name("Basic Machine Learning (online courses, side projects)") == (
        "Machine Learning"
    )


def test_unknown_names_pass_through():
    assert normalize_name("Terraform") == "Terraform"
    assert normalize_name("Snowflake") == "Snowflake"


def test_normalize_profile_dedupes_collapsed_names():
    profile = CVProfile(
        person_name="Test Person",
        headline="Engineer",
        summary="",
        skills=[
            EvidencedItem(name="AWS", evidence="a"),
            EvidencedItem(name="Amazon Web Services", evidence="b"),
        ],
        technologies=[],
        domains=["AI", "Artificial Intelligence"],
        projects=[],
        experience=[],
        education=[],
    )
    normalized = normalize_profile(profile)
    assert [s.name for s in normalized.skills] == ["AWS"]
    assert normalized.domains == ["Artificial Intelligence"]
