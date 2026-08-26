"""规则优先意图。模糊且有 Chat Key 时才走 LLM。"""

from __future__ import annotations

import json
import re
from typing import Any

from config.settings import get_settings
from smc.rag.alias import canonical_terms
from smc.rag.link import link_from_query
from smc.safety.rules import classify_input

_CHITCHAT = (
    "你好", "您好", "hello", "hi", "谢谢", "感谢", "再见", "拜拜",
    "你是谁", "你谁", "天气", "笑话", "哈哈",
)
_TRIAGE = (
    "挂哪", "看什么科", "哪个科", "去哪个科", "挂什么科", "看哪科",
    "去什么科", "什么科室", "挂什么科室", "看什么科室", "该挂", "该看哪",
    "看哪个科", "挂哪个",
)
_PREP = ("带什么", "准备", "空腹", "就诊前", "问诊时", "复诊")
_KNOW = ("是什么", "什么区别", "注意事项", "怎么定义", "科普", "注意什么", "介绍一下")
_MED = ("说明书", "副作用", "什么药", "药品", "阿司匹林", "他汀")


def rule_intent(query: str) -> str | None:
    cls = classify_input(query)
    if cls in {"emergency", "refuse"}:
        return cls
    q = query or ""
    ql = q.lower()
    if any(m in q or m in ql for m in _CHITCHAT) and not canonical_terms(q):
        return "chitchat"
    if any(m in q for m in _PREP):
        return "visit_prep"
    if any(m in q for m in _MED):
        return "medication_info"
    if any(m in q for m in _KNOW):
        return "knowledge"
    if any(m in q for m in _TRIAGE) or canonical_terms(q) or link_from_query(q):
        return "triage"
    if re.search(r"(疼|痛|痒|咳|烧|酸|晕|涕|泻|疹)", q) and "药" not in q:
        return "triage"
    return None


def llm_intent(query: str) -> str | None:
    from smc.agents.llm import chat_complete

    prompt = (
        "只输出 JSON：{\"intent\": \"triage|visit_prep|knowledge|medication_info|chitchat|refuse|emergency\"}。\n"
        "导诊=问挂哪科；就诊准备=去医院带什么；科普=疾病/检查说明；"
        "药品说明=药是什么/副作用（不是开药）；拒答=要开药/剂量/确诊；急诊=急症；闲聊=其他。\n"
        f"用户：{query}"
    )
    raw = chat_complete([{"role": "user", "content": prompt}], max_tokens=40)
    if not raw:
        return None
    try:
        data = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        intent = data.get("intent")
        allowed = {
            "triage",
            "visit_prep",
            "knowledge",
            "medication_info",
            "chitchat",
            "refuse",
            "emergency",
        }
        if intent in allowed:
            return str(intent)
    except Exception:
        return None
    return None


def detect_intent(query: str, allow_llm: bool = True) -> str:
    hit = rule_intent(query)
    if hit:
        return hit
    if allow_llm and get_settings().chat_api_key:
        guessed = llm_intent(query)
        if guessed:
            return guessed
    return "chitchat"


def extract_entities(query: str) -> dict[str, list[str]]:
    terms = link_from_query(query)
    return {"symptoms": terms, "diseases": terms, "drugs": []}
