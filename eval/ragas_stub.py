"""RAGAS / LLM-as-judge 接口。板块二能出完整回答后再接真实评分。"""

from __future__ import annotations

from typing import Any


def evaluate_answers(_samples: list[dict[str, Any]]) -> dict[str, float]:
    """占位：返回空指标，避免 CI 依赖生成链路。"""
    return {
        "faithfulness": None,
        "context_precision": None,
        "status": "not_implemented_until_agent",
    }
