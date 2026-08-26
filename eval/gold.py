"""校验 eval/gold_v0.json 格式与覆盖度。用法：在仓库根目录执行 python -m eval.gold"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

INTENTS = frozenset(
    {
        "emergency",
        "triage",
        "visit_prep",
        "knowledge",
        "medication_info",
        "chitchat",
        "refuse",
    }
)
DEPT_OR_REFUSE_SPECIAL = frozenset({"refuse", "emergency_referral", "chitchat"})
REQUIRED = ("id", "query", "intent", "expect_dept_or_refuse", "must_cite", "emergency")
MIN_ITEMS = 50
MIN_PER_INTENT = {
    "emergency": 8,
    "triage": 12,
    "visit_prep": 5,
    "knowledge": 6,
    "chitchat": 4,
    "refuse": 6,
}


def gold_path() -> Path:
    return Path(__file__).resolve().parent / "gold_v0.json"


def load_gold(path: Path | None = None) -> dict:
    raw = json.loads((path or gold_path()).read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return {"version": "unknown", "items": raw}
    if not isinstance(raw, dict) or "items" not in raw:
        raise ValueError("gold 文件必须是 {items: [...]} 或数组")
    return raw


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    items = data.get("items") or []
    if len(items) < MIN_ITEMS:
        errors.append(f"条目数 {len(items)} < {MIN_ITEMS}")

    ids: set[str] = set()
    counts: Counter[str] = Counter()

    for i, item in enumerate(items):
        loc = item.get("id") or f"index={i}"
        for key in REQUIRED:
            if key not in item:
                errors.append(f"{loc}: 缺字段 {key}")
        intent = item.get("intent")
        if intent not in INTENTS:
            errors.append(f"{loc}: 非法 intent={intent!r}")
        else:
            counts[intent] += 1

        item_id = item.get("id")
        if not item_id:
            errors.append(f"index={i}: id 为空")
        elif item_id in ids:
            errors.append(f"{item_id}: id 重复")
        else:
            ids.add(item_id)

        if not isinstance(item.get("query"), str) or not str(item.get("query")).strip():
            errors.append(f"{loc}: query 为空")
        if not isinstance(item.get("must_cite"), bool):
            errors.append(f"{loc}: must_cite 必须是 bool")
        if not isinstance(item.get("emergency"), bool):
            errors.append(f"{loc}: emergency 必须是 bool")

        dest = item.get("expect_dept_or_refuse")
        if not isinstance(dest, str) or not dest.strip():
            errors.append(f"{loc}: expect_dept_or_refuse 为空")

        if item.get("emergency") is True:
            if intent != "emergency":
                errors.append(f"{loc}: emergency=true 时 intent 必须是 emergency")
            if dest != "emergency_referral":
                errors.append(f"{loc}: emergency=true 时 dest 必须是 emergency_referral")
            if item.get("must_cite") is True:
                errors.append(f"{loc}: 急诊路径不得要求 must_cite")

        if intent == "chitchat" and dest != "chitchat":
            errors.append(f"{loc}: chitchat 的 dest 必须是 chitchat")
        if intent == "refuse" and dest != "refuse":
            errors.append(f"{loc}: refuse 的 dest 必须是 refuse")
        if intent == "triage" and dest in DEPT_OR_REFUSE_SPECIAL:
            errors.append(f"{loc}: triage 应给科室名，不能是 {dest}")

    for intent, minimum in MIN_PER_INTENT.items():
        if counts[intent] < minimum:
            errors.append(f"覆盖不足: {intent} 仅 {counts[intent]} 条，至少 {minimum}")

    return errors


def main() -> int:
    path = gold_path()
    data = load_gold(path)
    errors = validate(data)
    items = data["items"]
    counts = Counter(x["intent"] for x in items)
    print(f"gold={path.name} version={data.get('version')} n={len(items)}")
    for key in sorted(counts):
        print(f"  {key}: {counts[key]}")
    if errors:
        print("FAIL")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
