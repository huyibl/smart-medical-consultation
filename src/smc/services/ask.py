"""问答入口，事件形状对齐 CONTRACTS SSE。"""

from __future__ import annotations

import uuid
from typing import Any, Iterator

from smc.graph.nodes import set_store
from smc.graph.workflow import build_workflow

_APP = None


def reset_app() -> None:
    global _APP
    _APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = build_workflow()
    return _APP


def ask(
    query: str,
    store=None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    if store is not None:
        set_store(store)
    request_id = uuid.uuid4().hex[:12]
    messages = [m for m in (history or []) if m.get("role") and m.get("content")]
    messages.append({"role": "user", "content": query})
    result = _app().invoke(
        {
            "request_id": request_id,
            "query": query,
            "messages": messages,
            "trace": [],
            "sources": [],
            "department_candidates": [],
            "emergency": False,
        }
    )
    return result


def events_from_result(result: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for item in result.get("trace") or []:
        yield {
            "type": "trace",
            "node": item.get("node"),
            "status": "done",
            "elapsed_ms": item.get("elapsed_ms"),
        }
    sources = [
        {"source_id": s.get("source_id"), "kind": s.get("kind"), "title": s.get("title")}
        for s in (result.get("sources") or [])
    ]
    if sources:
        yield {"type": "sources", "items": sources}
    answer = result.get("answer") or ""
    step = 12
    for i in range(0, len(answer), step):
        yield {"type": "token", "text": answer[i : i + step]}
    safety = result.get("safety") or {}
    yield {
        "type": "safety",
        "blocked": safety.get("blocked"),
        "rule_ids": safety.get("rule_ids"),
        "emergency": result.get("emergency"),
    }
    yield {
        "type": "done",
        "intent": result.get("intent"),
        "department_candidates": result.get("department_candidates") or [],
        "request_id": result.get("request_id"),
        "elapsed_ms": sum(int(t.get("elapsed_ms") or 0) for t in (result.get("trace") or [])),
    }


def ask_events(
    query: str,
    store=None,
    history: list[dict[str, str]] | None = None,
) -> Iterator[dict[str, Any]]:
    result = ask(query, store=store, history=history)
    yield from events_from_result(result)
