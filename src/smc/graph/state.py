"""LangGraph 共享状态，字段与 docs/CONTRACTS.md 对齐。"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    request_id: str
    query: str
    messages: list[dict[str, str]]
    intent: str | None
    emergency: bool
    entities: dict[str, list[str]]
    retrieval: dict[str, list[Any]]
    sources: list[dict[str, str]]
    department_candidates: list[str]
    generator_output: str
    safety: dict[str, Any]
    answer: str
    trace: list[dict[str, Any]]
    skip_retrieve: bool
    retrieve_mode: str
