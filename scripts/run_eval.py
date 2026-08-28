"""Evaluate TalentGraph against tests/eval/queries.yaml.

Scores the dimensions the requirements specification asks for: intent
classification accuracy, candidate retrieval precision/recall/F1, answer
groundedness signals, and response latency.

Run it through the backend environment (it imports the app for in-process mode):

    make eval                                                  # in-process
    cd backend && uv run python ../scripts/run_eval.py --url https://<site>
    cd backend && uv run python ../scripts/run_eval.py --markdown ../report.md
"""

import argparse
import json
import statistics
import sys
import time
import uuid
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
QUERIES = REPO_ROOT / "tests" / "eval" / "queries.yaml"


def ask_local(message: str, conversation_id: str) -> dict:
    """Call the service directly, no HTTP server required."""
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from app.service import handle_chat  # noqa: PLC0415 — needs the path above

    return handle_chat(message, conversation_id).model_dump()


def ask_http(url: str):
    import httpx  # noqa: PLC0415 — only needed in --url mode

    client = httpx.Client(timeout=180)

    def _ask(message: str, conversation_id: str) -> dict:
        response = client.post(
            f"{url.rstrip('/')}/chat",
            json={"message": message, "conversation_id": conversation_id},
        )
        response.raise_for_status()
        return response.json()

    return _ask


def score_case(case: dict, response: dict) -> dict:
    answer = response.get("answer", "")
    expected_people = case.get("people")
    expected_intent = case.get("intent")

    result = {
        "id": case["id"],
        "query": case["query"],
        "intent_expected": expected_intent,
        "intent_actual": response.get("intent"),
        "intent_ok": expected_intent is None or response.get("intent") == expected_intent,
        "evidence_count": len(response.get("evidence", [])),
    }

    # Retrieval quality: does the prose name the people it should, and only those?
    # Precision is a strict lower bound — a name counts against it wherever it
    # appears, including in legitimate "X has Python but not AWS" commentary. Treat
    # the `spurious` list as items for human review, not confirmed errors.
    if expected_people is not None:
        named = {p for p in all_people(case) if p in answer}
        expected = set(expected_people)
        true_positives = len(named & expected)
        if named:
            result["precision"] = true_positives / len(named)
        else:
            # Naming nobody is correct only when nobody was expected.
            result["precision"] = 1.0 if not expected else 0.0
        result["recall"] = true_positives / len(expected) if expected else 1.0
        result["missing"] = sorted(expected - named)
        result["spurious"] = sorted(named - expected)

    missing_mentions = [m for m in case.get("must_mention", []) if m.lower() not in answer.lower()]
    result["mentions_ok"] = not missing_mentions
    result["missing_mentions"] = missing_mentions

    # Groundedness proxy: a factual answer should cite graph relationships.
    result["grounded"] = result["evidence_count"] > 0 or expected_intent == "GENERAL"
    return result


def all_people(case: dict) -> set[str]:
    """Every person name in the eval set — needed to detect spurious names."""
    return _ALL_PEOPLE | set(case.get("people", []))


def f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TalentGraph evaluation set")
    parser.add_argument("--url", help="Evaluate a running API instead of in-process")
    parser.add_argument("--markdown", type=Path, help="Write a Markdown report here")
    parser.add_argument("--json", type=Path, help="Write raw results here")
    parser.add_argument("--only", help="Run a single case by id")
    args = parser.parse_args()

    cases = yaml.safe_load(QUERIES.read_text(encoding="utf-8"))
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]
        if not cases:
            raise SystemExit(f"No eval case with id {args.only!r}")

    global _ALL_PEOPLE
    _ALL_PEOPLE = {p for c in cases for p in c.get("people", [])}

    ask = ask_http(args.url) if args.url else ask_local
    conversations: dict[str, str] = {}
    results, latencies = [], []

    print(
        f"Running {len(cases)} evaluation cases"
        f"{' against ' + args.url if args.url else ' in-process'}\n"
    )

    for case in cases:
        # Follow-ups must share the earlier case's conversation to test history.
        parent = case.get("follow_up_of")
        conversation_id = conversations.get(parent) or f"eval-{uuid.uuid4().hex[:8]}"
        conversations[case["id"]] = conversation_id

        started = time.perf_counter()
        try:
            response = ask(case["query"], conversation_id)
        except Exception as err:  # noqa: BLE001 — one bad case shouldn't end the run
            print(f"  ✗ {case['id']:<22} ERROR {err}")
            results.append({"id": case["id"], "error": str(err), "intent_ok": False})
            continue
        latency = time.perf_counter() - started
        latencies.append(latency)

        result = score_case(case, response)
        result["latency_s"] = round(latency, 2)
        results.append(result)

        checks = [result["intent_ok"], result["mentions_ok"], result.get("recall", 1.0) == 1.0]
        mark = "✓" if all(checks) else "✗"
        detail = f"intent={result['intent_actual']}"
        if "recall" in result:
            detail += f" P={result['precision']:.2f} R={result['recall']:.2f}"
        print(f"  {mark} {case['id']:<22} {detail}  {latency:.1f}s")
        if result.get("missing"):
            print(f"      missing people:  {', '.join(result['missing'])}")
        if result.get("spurious"):
            print(f"      spurious people: {', '.join(result['spurious'])}")
        if result.get("missing_mentions"):
            print(f"      missing mentions: {', '.join(result['missing_mentions'])}")

    scored = [r for r in results if "error" not in r]
    retrieval = [r for r in scored if "precision" in r]
    summary = {
        "cases": len(results),
        "errors": len(results) - len(scored),
        "intent_accuracy": mean([r["intent_ok"] for r in scored]),
        "precision": mean([r["precision"] for r in retrieval]),
        "recall": mean([r["recall"] for r in retrieval]),
        "mention_accuracy": mean([r["mentions_ok"] for r in scored]),
        "groundedness": mean([r["grounded"] for r in scored]),
        "latency_mean_s": round(statistics.mean(latencies), 2) if latencies else 0.0,
        "latency_p95_s": round(max(latencies), 2) if latencies else 0.0,
    }
    summary["f1"] = round(f1(summary["precision"], summary["recall"]), 3)

    print("\n" + "─" * 58)
    print(f"  Intent accuracy      {summary['intent_accuracy']:.1%}")
    print(f"  Retrieval precision  {summary['precision']:.1%}  (strict lower bound)")
    print(f"  Retrieval recall     {summary['recall']:.1%}")
    print(f"  Retrieval F1         {summary['f1']:.3f}")
    print(f"  Required mentions    {summary['mention_accuracy']:.1%}")
    print(f"  Grounded answers     {summary['groundedness']:.1%}")
    print(f"  Latency mean / max   {summary['latency_mean_s']}s / {summary['latency_p95_s']}s")
    if summary["errors"]:
        print(f"  Errors               {summary['errors']}")
    print("─" * 58)
    print(
        "\nCost: ~2 gpt-5-mini calls per query (classify + synthesise); see the "
        "OpenAI dashboard for exact spend."
    )

    if args.json:
        args.json.write_text(json.dumps({"summary": summary, "results": results}, indent=2))
        print(f"\nWrote {args.json}")
    if args.markdown:
        args.markdown.write_text(markdown_report(summary, results), encoding="utf-8")
        print(f"Wrote {args.markdown}")


def mean(values: list) -> float:
    return (
        round(sum(1 if v is True else 0 if v is False else v for v in values) / len(values), 3)
        if values
        else 0.0
    )


def markdown_report(summary: dict, results: list[dict]) -> str:
    lines = [
        "# TalentGraph — Evaluation Report",
        "",
        "| Metric | Score |",
        "| --- | --- |",
        f"| Intent classification accuracy | {summary['intent_accuracy']:.1%} |",
        f"| Candidate retrieval precision (strict) | {summary['precision']:.1%} |",
        f"| Candidate retrieval recall | {summary['recall']:.1%} |",
        f"| Retrieval F1 | {summary['f1']:.3f} |",
        f"| Required-mention accuracy | {summary['mention_accuracy']:.1%} |",
        f"| Grounded answers (evidence attached) | {summary['groundedness']:.1%} |",
        f"| Mean latency | {summary['latency_mean_s']} s |",
        f"| Max latency | {summary['latency_p95_s']} s |",
        f"| Cases | {summary['cases']} |",
        "",
        "Precision is a **strict lower bound**: a person's name counts against it "
        "wherever it appears in the answer, including legitimate near-miss "
        'commentary such as *"Kevin Wong has Python but not AWS"*. Recall is the '
        "reliable signal for whether retrieval found everyone it should.",
        "",
        "## Per-case results",
        "",
        "| Case | Intent | P | R | Latency | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        if "error" in r:
            lines.append(f"| {r['id']} | ERROR | — | — | — | — |")
            continue
        precision = f"{r['precision']:.2f}" if "precision" in r else "—"
        recall = f"{r['recall']:.2f}" if "recall" in r else "—"
        intent = ("✓ " if r["intent_ok"] else "✗ ") + str(r["intent_actual"])
        lines.append(
            f"| {r['id']} | {intent} | {precision} | {recall} | "
            f"{r['latency_s']}s | {r['evidence_count']} |"
        )
    return "\n".join(lines) + "\n"


_ALL_PEOPLE: set[str] = set()

if __name__ == "__main__":
    main()
