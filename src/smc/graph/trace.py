"""节点耗时与预览。"""

from __future__ import annotations

import time
from typing import Any


def now_ms() -> int:
    return int(time.time() * 1000)


def append_trace(
    state: dict[str, Any],
    node: str,
    started_ms: int,
    output_preview: str,
    input_preview: str = "",
) -> list[dict[str, Any]]:
    item = {
        "node": node,
        "started_ms": started_ms,
        "elapsed_ms": now_ms() - started_ms,
        "input_preview": (input_preview or state.get("query") or "")[:80],
        "output_preview": (output_preview or "")[:160],
    }
    return list(state.get("trace") or []) + [item]
