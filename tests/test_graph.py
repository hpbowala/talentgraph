from app.graph.retriever import coverage, find_paths, find_people, get_person_profile


def test_roundtrip_nodes_and_types(kg):
    assert kg.node_type("Alice Perera") == "person"
    assert kg.node_type("Python") == "skill"
    assert kg.node_type("FastAPI") == "technology"
    assert kg.node_type("Customer Support AI") == "project"
    assert kg.node_type("Artificial Intelligence") == "domain"
    assert kg.node_type("University of Moratuwa") == "education"


def test_person_edges(kg):
    profile = get_person_profile(kg, "Alice Perera")
    assert {e["target"] for e in profile["HAS_SKILL"]} == {"Python", "AWS", "NLP"}
    assert {e["target"] for e in profile["USES"]} == {"FastAPI"}
    assert {e["target"] for e in profile["WORKED_ON"]} == {"Customer Support AI"}
    assert {e["target"] for e in profile["EXPERIENCE_IN"]} == {
        "Artificial Intelligence"
    }
    assert {e["target"] for e in profile["STUDIED"]} == {"University of Moratuwa"}


def test_project_edges(kg):
    assert any(
        t == "LangChain" and d["relation"] == "USES"
        for _, t, d in kg.out_edges("Customer Support AI")
    )
    assert any(
        t == "Artificial Intelligence" and d["relation"] == "IN_DOMAIN"
        for _, t, d in kg.out_edges("Customer Support AI")
    )


def test_related_skills_from_cooccurrence(kg):
    # Alice and Bob both hold Python and AWS -> RELATED_TO edge between them.
    assert any(
        t == "AWS" and d["relation"] == "RELATED_TO"
        for _, t, d in kg.out_edges("Python")
    )


def test_find_people_match_all(kg):
    matches = find_people(kg, capabilities=["Python", "NLP"], match="all")
    assert [m.person for m in matches] == ["Alice Perera"]
    assert "Alice Perera —HAS_SKILL→ NLP" in matches[0].matched["NLP"]


def test_find_people_match_any_ranks_by_score(kg):
    matches = find_people(kg, capabilities=["Python", "NLP"], match="any")
    assert [m.person for m in matches] == ["Alice Perera", "Bob Silva"]
    assert matches[1].missing == ["NLP"]


def test_find_people_alias_resolution(kg):
    matches = find_people(kg, capabilities=["amazon web services"], match="all")
    assert {m.person for m in matches} == {"Alice Perera", "Bob Silva"}


def test_find_paths_person_to_skill(kg):
    paths = find_paths(kg, "Alice Perera", "NLP")
    assert paths and "Alice Perera —HAS_SKILL→ NLP" in paths[0]


def test_find_paths_between_people(kg):
    paths = find_paths(kg, "Alice Perera", "Bob Silva")
    assert paths  # connected via shared Python/AWS skills
    assert any("Python" in p or "AWS" in p for p in paths)


def test_coverage_reports_gaps(kg):
    result = coverage(kg, ["Python", "React"], ["Alice Perera", "Bob Silva"])
    assert result["covered"]["Python"] == ["Alice Perera", "Bob Silva"]
    assert "React" in result["gaps"]


def test_fuzzy_person_resolution(kg):
    assert kg.resolve("alice") == "Alice Perera"
    assert kg.resolve("Alice Perera") == "Alice Perera"
    assert kg.resolve("aws") == "AWS"
