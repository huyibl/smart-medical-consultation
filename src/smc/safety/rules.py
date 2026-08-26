"""从 config/safety_rules.yaml 加载的纯规则引擎。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from config.settings import PROJECT_ROOT

_SKIP_CHARS = "的地得了着过也都还就很太吗呢啊呀么嘛，。！？、；： \t\n"


@lru_cache
def load_safety_rules(path: Path | None = None) -> dict[str, Any]:
    p = path or (PROJECT_ROOT / "config" / "safety_rules.yaml")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("safety_rules.yaml 无效")
    return data


def normalize(text: str) -> str:
    out = text or ""
    for ch in _SKIP_CHARS:
        out = out.replace(ch, "")
    return out


_NEG = ("没有", "无", "不是", "并非", "不像")


def _negated(text: str, idx: int) -> bool:
    prefix = text[max(0, idx - 4) : idx]
    return any(n in prefix for n in _NEG)


def _hit_any(text: str, keywords: list[str]) -> str | None:
    raw = text or ""
    folded = normalize(raw)
    for kw in keywords:
        if not kw:
            continue
        start = 0
        while True:
            idx = raw.find(kw, start)
            if idx < 0:
                break
            if not _negated(raw, idx):
                return kw
            start = idx + len(kw)
        nkw = normalize(kw)
        if nkw and nkw in folded:
            idx = folded.find(nkw)
            # 折叠后否定词可能被删掉，只信原文未命中时的折叠匹配
            if idx >= 0 and kw not in raw:
                return kw
    return None


def classify_input(query: str, rules: dict[str, Any] | None = None) -> str:
    """emergency | refuse | other。急诊优先。"""
    cfg = rules or load_safety_rules()
    if _hit_any(query, list(cfg.get("emergency", {}).get("keywords") or [])):
        return "emergency"
    if _hit_any(query, list(cfg.get("refuse_triggers", {}).get("keywords") or [])):
        return "refuse"
    return "other"


def emergency_reply() -> str:
    cfg = load_safety_rules()
    extra = (cfg.get("disclaimer") or {}).get("text") or ""
    return (
        "你描述的情况可能属于急症，我不能在线处理，也不能给出诊断或急救操作方案。"
        "请立即拨打当地急救电话或前往最近的医院急诊。\n"
        + extra.strip()
    )


def review_output(
    answer: str,
    *,
    intent: str = "triage",
    medication: bool = False,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """检查声明、禁句、急诊文案。rule_ids 非空表示未过门禁。"""
    cfg = rules or load_safety_rules()
    failed: list[str] = []
    disc = cfg.get("disclaimer") or {}
    required = set(disc.get("required_for") or [])
    if intent in required:
        needles = list(disc.get("must_contain_any") or [])
        if not any(n in (answer or "") for n in needles):
            failed.append("R-DISCLAIMER")
    if medication and "遵医嘱" not in (answer or "") and "药师" not in (answer or ""):
        failed.append("R-MED-FOLLOW-DOCTOR")
    banned = list((cfg.get("output_banned") or {}).get("phrases") or [])
    hit = _hit_any(answer, banned)
    if hit:
        if hit in {"确诊", "诊断你是", "你就是", "可以确定是"}:
            failed.append("R-NO-DIAGNOSIS")
        else:
            failed.append("R-NO-PRESCRIPTION")
    if intent == "emergency":
        must = list((cfg.get("emergency") or {}).get("must_contain") or [])
        if not any(x in (answer or "") for x in must):
            failed.append("R-EMERGENCY-RECALL")
        forbid = list((cfg.get("emergency") or {}).get("must_not_contain") or [])
        if _hit_any(answer, forbid):
            failed.append("R-EMERGENCY-RECALL")
    return {"ok": not failed, "rule_ids": list(dict.fromkeys(failed))}
