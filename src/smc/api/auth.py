"""鉴权与内存限流。无 Key → 401；超限 → 429。"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

def _is_public(path: str) -> bool:
    if path in {"/", "/health", "/openapi.json", "/docs", "/redoc"}:
        return True
    return path.startswith("/docs") or path.startswith("/redoc")


def extract_api_key(request: Request) -> str | None:
    raw = request.headers.get("X-API-Key")
    if raw and raw.strip():
        return raw.strip()
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        return token or None
    return None


def parse_api_keys(raw: str) -> set[str]:
    return {k.strip() for k in (raw or "").split(",") if k.strip()}


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = max(0, int(per_minute))
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.per_minute <= 0:
            return True
        now = time.monotonic()
        window = now - 60.0
        with self._lock:
            q = self._hits[key]
            while q and q[0] < window:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            return True


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, api_keys: set[str], limiter: RateLimiter):
        super().__init__(app)
        self.api_keys = api_keys
        self.limiter = limiter

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if _is_public(path) or not path.startswith("/v1"):
            return await call_next(request)
        key = extract_api_key(request)
        if not key or key not in self.api_keys:
            return JSONResponse(
                status_code=401,
                content={"code": "unauthorized", "message": "缺少或无效的 API Key"},
            )
        if not self.limiter.allow(key):
            return JSONResponse(
                status_code=429,
                content={"code": "rate_limited", "message": "请求过于频繁，请稍后再试"},
            )
        request.state.api_key = key
        return await call_next(request)
