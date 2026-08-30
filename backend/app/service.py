"""Core chat service shared by the local FastAPI server and the AgentCore
entrypoint. Conversations are persisted to DynamoDB; the CV corpus and the graph
built from it live in the CV store (app/cv_store.py)."""

import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app import conversation_store, cv_store
from app.agents.orchestrator import build_orchestrator
from app.agents.state import HistoryTurn
from app.graph import loader
from app.graph.loader import load_graph
from app.graph.snapshot import build_snapshot
from app.ingest.extract_text import extract_text
from app.ingest.reindex import cv_person_names, reindex
from app.llm.provider import LLMProvider
from app.models import (
    ChatResponse,
    ConversationDetail,
    ConversationSummary,
    ConversationTurn,
    CVLibrary,
    CVSummary,
    EvidenceRef,
    GraphSnapshot,
)

TITLE_MAX_CHARS = 60
MAX_EVIDENCE = 60

_orchestrator = None
_graph = None
_provider: LLMProvider | None = None
_graph_stamp: str | None = None


def _get_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        _provider = LLMProvider()
    return _provider


def _get_graph():
    """Loaded once per index build. The stamp lives with the vault, so a CV
    uploaded through another runtime instance invalidates this one too."""
    global _graph, _orchestrator, _graph_stamp
    try:
        stamp = cv_store.index_stamp()
    except Exception:  # noqa: BLE001 — an unreadable manifest must not break chat
        stamp = _graph_stamp
    if _graph is None or stamp != _graph_stamp:
        _graph = load_graph(force_reload=loader.cached_stamp() != stamp)
        _orchestrator = None  # bound to the graph it was built over
        _graph_stamp = stamp
    return _graph


def _get_orchestrator():
    """Rebuilt whenever the graph underneath it changes."""
    global _orchestrator
    graph = _get_graph()
    if _orchestrator is None:
        _orchestrator = build_orchestrator(graph, _get_provider())
    return _orchestrator


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def derive_title(first_message: str) -> str:
    title = " ".join(first_message.split())
    if len(title) > TITLE_MAX_CHARS:
        title = title[: TITLE_MAX_CHARS - 1].rstrip() + "…"
    return title or "New conversation"


def history_from_turns(turns: list[dict]) -> list[HistoryTurn]:
    return [
        {
            "user": turn.get("user", ""),
            "answer": turn.get("answer", ""),
            "entities": list(turn.get("entities", [])),
        }
        for turn in turns
    ]


def handle_chat(message: str, conversation_id: str | None = None) -> ChatResponse:
    conversation_id = conversation_id or f"conv-{uuid.uuid4()}"
    now = _now()
    conversation = conversation_store.fetch(conversation_id) or {
        "conversation_id": conversation_id,
        "title": derive_title(message),
        "created_at": now,
        "turns": [],
    }

    orchestrator = _get_orchestrator()
    state = orchestrator.invoke(
        {
            "conversation_id": conversation_id,
            "user_query": message,
            "history": history_from_turns(conversation["turns"]),
            "agent_results": {},
            "evidence": [],
            "retrieved_nodes": [],
            "graph_paths": [],
        }
    )

    answer = state.get("final_answer", "I could not produce an answer for that question.")
    entities = sorted(set(state.get("retrieved_nodes", [])))

    seen: set[str] = set()
    evidence = []
    for e in state.get("evidence", []):
        if e["detail"] not in seen:
            seen.add(e["detail"])
            evidence.append(EvidenceRef(**e))
        if len(evidence) >= MAX_EVIDENCE:
            break

    conversation["turns"].append(
        {
            "user": message,
            "answer": answer,
            "intent": state.get("intent", "GENERAL"),
            "evidence": [e.model_dump() for e in evidence],
            "entities": entities,
            "ts": now,
        }
    )
    conversation["updated_at"] = now
    conversation_store.save(conversation)

    return ChatResponse(
        answer=answer,
        intent=state.get("intent", "GENERAL"),
        evidence=evidence,
        conversation_id=conversation_id,
    )


def list_conversations() -> list[ConversationSummary]:
    return [
        ConversationSummary(
            conversation_id=item["conversation_id"],
            title=item.get("title", "Untitled"),
            updated_at=item.get("updated_at", ""),
        )
        for item in conversation_store.list_summaries()
    ]


def get_conversation(conversation_id: str) -> ConversationDetail | None:
    item = conversation_store.fetch(conversation_id)
    if item is None:
        return None
    return ConversationDetail(
        conversation_id=item["conversation_id"],
        title=item.get("title", "Untitled"),
        turns=[ConversationTurn(**turn) for turn in item.get("turns", [])],
    )


def delete_conversation(conversation_id: str) -> None:
    conversation_store.delete(conversation_id)


# ---------- knowledge graph ----------


def graph_snapshot() -> GraphSnapshot:
    """The whole graph as nodes and edges, for the frontend explorer.

    Reads the same in-process graph the agents traverse.
    """
    return build_snapshot(_get_graph(), indexed_at=_graph_stamp)


# ---------- CV library ----------


def list_cvs() -> CVLibrary:
    people = cv_person_names()
    return CVLibrary(
        cvs=[
            CVSummary(
                filename=record.filename,
                size_bytes=record.size_bytes,
                uploaded_at=record.uploaded_at,
                person=people.get(record.filename),
            )
            for record in cv_store.list_cvs()
        ],
        indexed_at=cv_store.index_stamp(),
    )


def add_cv(filename: str, content: bytes) -> CVLibrary:
    """Validate and store an uploaded CV.

    Making the CV answerable is not fast, so the caller triggers
    reindex_library() separately and the UI polls list_cvs() for the new stamp.
    """
    filename = cv_store.safe_filename(filename)
    cv_store.check_size(content)
    _require_readable_text(filename, content)
    cv_store.put_cv(filename, content)
    return list_cvs()


def delete_cv(filename: str) -> CVLibrary:
    """Remove a CV from the store. Reindexing drops it from the graph."""
    filename = cv_store.safe_filename(filename)
    if not cv_store.delete_cv(filename):
        raise cv_store.CVStoreError(f"No CV named {filename} in the library.")
    return list_cvs()


def reindex_library() -> CVLibrary:
    """Rebuild the graph from the stored CVs. Minutes, not seconds — run it in
    the background (BackgroundTasks locally, an async Lambda invoke in AWS)."""
    global _orchestrator, _graph, _graph_stamp

    report = reindex(provider=_get_provider())
    # Dropped, not rebuilt: the next question builds against the new graph.
    _orchestrator, _graph, _graph_stamp = None, None, None
    library = list_cvs()
    library.note_count = report.note_count
    return library


def _require_readable_text(filename: str, content: bytes) -> None:
    """Reject documents the extractor cannot read before they enter the store."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / filename
        path.write_bytes(content)
        try:
            text = extract_text(path)
        except Exception as err:  # noqa: BLE001 — surfaced to the uploader as a 400
            raise cv_store.CVStoreError(f"Could not read {filename}: {err}") from err
    if len(text.strip()) < 40:
        raise cv_store.CVStoreError(
            f"No readable text in {filename} — scanned or image-only CVs are not supported."
        )
