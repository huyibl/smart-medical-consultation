"""FastAPI：POST /v1/chat SSE，历史 SQLite。"""

from __future__ import annotations

import json
import logging
from typing import Any

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config.settings import Settings, get_settings
from smc import __version__
from smc.api.auth import AuthRateLimitMiddleware, RateLimiter, parse_api_keys
from smc.observability.log import chat_audit, setup_logging, setup_tracing
from smc.services.ask import ask, events_from_result
from smc.services.history import SqliteHistory, new_conversation_id, normalize_conversation_id

logger = logging.getLogger(__name__)

ALLOWED_EVENT_TYPES = frozenset({"trace", "token", "sources", "safety", "done", "error"})


class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    history: list[HistoryMessage] = Field(default_factory=list)


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def create_app(
    settings: Settings | None = None,
    store=None,
    history: SqliteHistory | None = None,
) -> FastAPI:
    cfg = settings or get_settings()
    setup_logging(cfg)
    setup_tracing(cfg)
    keys = parse_api_keys(cfg.api_keys)
    limiter = RateLimiter(cfg.rate_limit_per_minute)
    store_hist = history or SqliteHistory(cfg.sqlite_path, cfg.history_max_turns)

    app = FastAPI(
        title="智慧问诊 API",
        version=__version__,
        description="就医导诊与医学科普。不能替代执业医师。",
    )
    app.state.settings = cfg
    app.state.store = store
    app.state.history = store_hist
    app.add_middleware(
        AuthRateLimitMiddleware,
        api_keys=keys,
        limiter=limiter,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "smc", "version": __version__}

    @app.post("/v1/chat")
    def chat(req: ChatRequest, request: Request) -> StreamingResponse:
        query = req.query.strip()
        if not query:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_query", "message": "query 不能为空"},
            )
        cid_raw = req.conversation_id
        if cid_raw and not normalize_conversation_id(cid_raw):
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_conversation", "message": "conversation_id 格式无效"},
            )
        hist: SqliteHistory = request.app.state.history
        cid = hist.ensure(cid_raw or new_conversation_id())
        prior = hist.load_history(cid)
        if not prior and req.history:
            prior = [{"role": m.role, "content": m.content} for m in req.history]

        def gen():
            yield _sse({"type": "trace", "node": "chat", "status": "started", "elapsed_ms": 0})
            try:
                result = ask(query, store=request.app.state.store, history=prior)
            except Exception:
                logger.exception("chat failed")
                yield _sse({"type": "error", "code": "internal", "message": "服务暂时不可用"})
                return
            try:
                elapsed = sum(
                    int(t.get("elapsed_ms") or 0) for t in (result.get("trace") or [])
                )
                chat_audit(result, conversation_id=cid)
                hist.append_turn(
                    cid,
                    query,
                    result.get("answer") or "",
                    request_id=str(result.get("request_id") or ""),
                    intent=result.get("intent"),
                    sources=list(result.get("sources") or []),
                    safety=dict(result.get("safety") or {}),
                    extra={
                        "department_candidates": list(result.get("department_candidates") or []),
                        "elapsed_ms": elapsed,
                    },
                )
            except Exception:
                logger.exception("history persist failed")
            for event in events_from_result(result):
                if event.get("type") not in ALLOWED_EVENT_TYPES:
                    continue
                if event.get("type") == "done":
                    event = {**event, "conversation_id": cid}
                yield _sse(event)

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/v1/conversations")
    def list_conversations(request: Request, limit: int = 50) -> dict[str, Any]:
        hist: SqliteHistory = request.app.state.history
        return {"items": hist.list_conversations(limit=limit)}

    @app.get("/v1/conversations/{conversation_id}")
    def get_conversation(conversation_id: str, request: Request) -> dict[str, Any]:
        hist: SqliteHistory = request.app.state.history
        data = hist.get_conversation(conversation_id)
        if data is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "会话不存在"},
            )
        return data

    _mount_frontend(app, Path(cfg.frontend_dist))
    return app


_FRONTEND_HINT = """<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>智慧问诊</title></head>
<body style="font-family:sans-serif;max-width:40rem;margin:3rem auto;line-height:1.6">
<h1>智慧问诊 API 已启动</h1>
<p>对话页尚未构建。在仓库目录执行：</p>
<pre style="background:#f4f1ea;padding:1rem">cd frontend
npm install
npm run build</pre>
<p>然后重新 <code>python main.py serve</code>，打开本页即可使用。</p>
<p><a href="/docs">OpenAPI</a> · <a href="/health">health</a></p>
</body>
</html>
"""


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if not index.is_file():
        @app.get("/")
        def _hint() -> HTMLResponse:
            return HTMLResponse(_FRONTEND_HINT)
        return

    @app.get("/")
    def _index() -> FileResponse:
        return FileResponse(index)

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="fe-assets")

    @app.get("/{name:path}")
    def _spa(name: str):
        if name.startswith("v1") or name in {"health", "docs", "redoc", "openapi.json"}:
            raise HTTPException(status_code=404)
        candidate = (dist / name).resolve()
        root = dist.resolve()
        if candidate.is_file() and (candidate == root or root in candidate.parents):
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
