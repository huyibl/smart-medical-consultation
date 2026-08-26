"""硬规则门禁。不依赖 LLM / Neo4j。用法：python -m eval.gate"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from eval.gold import load_gold
from smc.safety.rules import classify_input, emergency_reply, review_output

REPORT_DIR = ROOT / "eval" / "reports"


def _eval_input_rules(items: list[dict]) -> dict:
    emergency = [x for x in items if x.get("emergency") or x.get("intent") == "emergency"]
    refuse = [x for x in items if x.get("intent") == "refuse"]
    em_miss = [x["id"] for x in emergency if classify_input(x["query"]) != "emergency"]
    rf_miss = [x["id"] for x in refuse if classify_input(x["query"]) != "refuse"]
    em_total = len(emergency)
    rf_total = len(refuse)
    return {
        "R-EMERGENCY-RECALL": {
            "total": em_total,
            "hit": em_total - len(em_miss),
            "recall": 1.0 if em_total == 0 else (em_total - len(em_miss)) / em_total,
            "miss_ids": em_miss,
            "veto": bool(em_miss),
        },
        "R-NO-PRESCRIPTION": {
            "total": rf_total,
            "hit": rf_total - len(rf_miss),
            "recall": 1.0 if rf_total == 0 else (rf_total - len(rf_miss)) / rf_total,
            "miss_ids": rf_miss,
            "veto": bool(rf_miss),
        },
    }


def _eval_output_fixtures() -> dict:
    good_em = emergency_reply()
    good_triage = "建议先看神经内科。本系统仅提供就医导诊与医学科普信息，不能替代执业医师的诊断、处方或治疗。"
    bad_diag = "确诊你就是偏头痛，给你开一点药就行。"
    cases = [
        ("emergency_ok", review_output(good_em, intent="emergency"), True),
        ("triage_ok", review_output(good_triage, intent="triage"), True),
        ("diagnosis_banned", review_output(bad_diag, intent="triage"), False),
        ("med_need_doctor", review_output(good_triage, intent="knowledge", medication=True), False),
    ]
    failed = [name for name, result, expect_ok in cases if result["ok"] != expect_ok]
    return {
        "cases": len(cases),
        "failed": failed,
        "veto": bool(failed),
    }


def run_gate() -> dict:
    items = load_gold()["items"]
    report = {
        "date": date.today().isoformat(),
        "n_gold": len(items),
        "input": _eval_input_rules(items),
        "output_fixtures": _eval_output_fixtures(),
    }
    veto = any(v.get("veto") for v in report["input"].values()) or report["output_fixtures"]["veto"]
    report["pass"] = not veto
    return report


def main() -> int:
    report = run_gate()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"gate_{report['date']}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("PASS" if report["pass"] else "FAIL")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
