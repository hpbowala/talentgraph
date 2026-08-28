"""Small shared helpers for agent nodes."""


def evidence_ref(kind: str, detail: str, source: str | None = None) -> dict:
    ref = {"kind": kind, "detail": detail}
    if source:
        ref["source"] = f"vault/{source}"
    return ref
