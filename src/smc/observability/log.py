"""结构化审计日志。改 LOG_JSON / LANGSMITH_* 不需要改业务代码。"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from config.settings import Settings

_CONFIGURED = False


def setup_logging(settings: Settings | None = None) -> None:
    global _CONFIGURED
    level = getattr(settings, "log_level", None) or os.environ.get("LOG_LEVEL", "INFO")
    use_json = bool(getattr(settings, "log_json", False))
    root = logging.getLogger()
    root.setLevel(str(level).upper())
    if _CONFIGURED:
        return
    handler = logging.StreamHandler()
    if use_json:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.handlers.clear()
    root.addHandler(handler)
    _CONFIGURED = True


def setup_tracing(settings: Settings) -> None:
    """有 Key 才打开 LangSmith；未装 SDK 时只写环境变量。"""
    if not (settings.langsmith_tracing and settings.langsmith_api_key):
        return
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.langsmith_project)
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "event", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def chat_audit(result: dict[str, Any], *, conversation_id: str = "") -> dict[str, Any]:
    """问答落盘字段：耗时、证据 ID、安全拦截。不含完整用户原文。"""
    sources = result.get("sources") or []
    safety = result.get("safety") or {}
    elapsed = sum(int(t.get("elapsed_ms") or 0) for t in (result.get("trace") or []))
    event = {
        "event": "chat",
        "request_id": result.get("request_id"),
        "conversation_id": conversation_id or None,
        "intent": result.get("intent"),
        "emergency": bool(result.get("emergency")),
        "elapsed_ms": elapsed,
        "source_ids": [s.get("source_id") for s in sources if s.get("source_id")],
        "departments": list(result.get("department_candidates") or []),
        "safety_blocked": bool(safety.get("blocked")),
        "rule_ids": list(safety.get("rule_ids") or []),
    }
    logging.getLogger("smc.audit").info("chat", extra={"event": event})
    return event
