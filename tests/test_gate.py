from eval.gate import run_gate
from eval.gold import load_gold
from smc.safety.rules import classify_input, emergency_reply, review_output


def test_gold_emergency_all_caught():
    items = [x for x in load_gold()["items"] if x.get("emergency")]
    missed = [x["id"] for x in items if classify_input(x["query"]) != "emergency"]
    assert missed == []


def test_gold_refuse_all_caught():
    items = [x for x in load_gold()["items"] if x.get("intent") == "refuse"]
    missed = [x["id"] for x in items if classify_input(x["query"]) != "refuse"]
    assert missed == []


def test_disclaimer_not_flagged_as_prescription():
    text = (
        "建议先看神经内科。"
        "本系统仅提供就医导诊与医学科普信息，不能替代执业医师的诊断、处方或治疗。"
    )
    assert review_output(text, intent="triage")["ok"] is True


def test_diagnosis_sentence_fails():
    bad = "确诊你就是偏头痛，给你开一点药。"
    result = review_output(bad, intent="triage")
    assert result["ok"] is False
    assert "R-NO-DIAGNOSIS" in result["rule_ids"] or "R-NO-PRESCRIPTION" in result["rule_ids"]


def test_emergency_reply_passes_output_gate():
    assert review_output(emergency_reply(), intent="emergency")["ok"] is True


def test_negation_not_emergency():
    assert classify_input("爬楼就心慌，没有胸痛，要看心内科吗") == "other"


def test_run_gate_pass():
    assert run_gate()["pass"] is True
