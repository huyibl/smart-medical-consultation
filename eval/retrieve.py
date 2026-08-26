"""金标导诊问句打向量库，写科室命中报告。用法：python -m eval.retrieve"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from eval.gold import load_gold
from smc.rag.retriever import search

REPORT_DIR = ROOT / "eval" / "reports"


def _dept_hit(hit: dict, expected: str, alts: list[str]) -> bool:
    names = [expected, *alts]
    names = [n for n in names if n and n not in {"refuse", "chitchat", "emergency_referral"}]
    blob = " ".join(
        [
            hit.get("text") or "",
            str((hit.get("metadata") or {}).get("department") or ""),
        ]
    )
    return any(n and n in blob for n in names)


def evaluate_retrieval(top_k: int = 5) -> dict:
    items = [x for x in load_gold()["items"] if x.get("intent") == "triage"]
    rows = []
    for item in items:
        expected = item.get("expect_dept_or_refuse") or ""
        alts = list(item.get("alt_depts") or [])
        t0 = time.perf_counter()
        hits = search(item["query"], top_k=top_k)
        latency = (time.perf_counter() - t0) * 1000
        hit1 = bool(hits) and _dept_hit(hits[0], expected, alts)
        hit3 = any(_dept_hit(h, expected, alts) for h in hits[:3])
        rows.append(
            {
                "id": item["id"],
                "query": item["query"],
                "expected": expected,
                "hit@1": hit1,
                "hit@3": hit3,
                "top_depts": [
                    (h.get("metadata") or {}).get("department") for h in hits[:3]
                ],
                "latency_ms": round(latency, 1),
            }
        )
    n = len(rows) or 1
    return {
        "date": date.today().isoformat(),
        "n": len(rows),
        "dept_hit@1": round(sum(1 for r in rows if r["hit@1"]) / n, 4),
        "dept_hit@3": round(sum(1 for r in rows if r["hit@3"]) / n, 4),
        "items": rows,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="检索评测")
    p.add_argument("--min-dept-recall", type=float, default=0.0, help="hit@3 下限；0 只出报告")
    p.add_argument("--top-k", type=int, default=5)
    args = p.parse_args(argv)
    try:
        report = evaluate_retrieval(top_k=args.top_k)
    except Exception as exc:
        print(f"SKIP retrieve: {exc}", file=sys.stderr)
        return 0
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"retrieve_{report['date']}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("date", "n", "dept_hit@1", "dept_hit@3")}, ensure_ascii=False, indent=2))
    print(f"wrote {out}")
    if report["dept_hit@3"] + 1e-9 < args.min_dept_recall:
        print(f"FAIL hit@3={report['dept_hit@3']} < {args.min_dept_recall}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
