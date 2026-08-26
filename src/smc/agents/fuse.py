"""基于证据生成。无检索则拒答；无 LLM 用模板。"""

from __future__ import annotations

from typing import Any

from config.settings import get_settings
from smc.agents.llm import chat_complete
from smc.safety.rules import emergency_reply, load_safety_rules

_TCM = {"中医综合", "中医科", "中医内科"}


def disclaimer() -> str:
    text = (load_safety_rules().get("disclaimer") or {}).get("text") or ""
    return str(text).strip()


def _dept_line(depts: list[str]) -> str:
    ordered = [d for d in depts if d and d not in _TCM]
    ordered += [d for d in depts if d in _TCM]
    seen: list[str] = []
    for d in ordered:
        if d not in seen:
            seen.append(d)
    if not seen:
        return ""
    return "、".join(seen[:3])


def template_answer(state: dict[str, Any]) -> str:
    intent = state.get("intent")
    if intent == "emergency":
        return emergency_reply()
    note = disclaimer()
    if intent == "refuse":
        return (
            "我不能开药、调整剂量、停药换药，也不能根据症状或检查单下诊断。"
            "请到线下由执业医师或药师处理。\n"
            + note
        )
    if intent == "chitchat":
        return (
            "我是就医导诊与医学科普助手，不能替代执业医师。"
            "可以直接说症状或病名，例如「最近头疼该挂哪科」「肝炎应该挂哪科」。"
        )
    sources = state.get("sources") or []
    depts = _dept_line(list(state.get("department_candidates") or []))
    if not sources:
        if intent == "medication_info":
            extra = (load_safety_rules().get("disclaimer") or {}).get("medication_extra") or ""
            return (
                "当前检索没有足够药品说明依据，请咨询执业医师或药师，不要自行用药。\n"
                + str(extra).strip()
                + "\n"
                + note
            )
        return (
            "图谱中没有匹配到你提到的病名或症状对应科室，建议到医院预检分诊或线下挂号，不要自行用药。\n"
            + note
        )
    titles = "；".join(
        f"{s.get('title') or s.get('source_id')}" for s in sources[:4]
    )
    if intent == "visit_prep":
        body = (
            "就诊前建议携带身份证和既往检查/用药记录，并记下症状出现的频率、持续时间和诱因。"
            + (f"相关科室常见为{depts}。" if depts else "")
        )
    elif intent == "medication_info":
        extra = (load_safety_rules().get("disclaimer") or {}).get("medication_extra") or ""
        body = (
            "下面仅列出检索到的药品公开信息，不是处方，也不能调整剂量。"
            + str(extra).strip()
        )
    elif intent == "knowledge":
        body = (
            "下面仅复述检索到的公开资料要点，不能据此确认你的病名。"
            + (f"资料中出现的科室包括{depts}。" if depts else "")
        )
    else:
        body = (
            f"根据公开资料，这类情况常见由{depts}接诊。"
            if depts
            else "根据公开资料可以做分诊参考，具体科室需面诊后确定。"
        )
        body += "若同时出现多个科室，请以医院预检分诊为准，不要把资料里的病名当成诊断。"
    return f"{body}\n来源：{titles}\n{note}"


def llm_answer(state: dict[str, Any]) -> str:
    sources = state.get("sources") or []
    evidence = "\n".join(
        f"- [{s.get('source_id')}] {s.get('title')}: {s.get('snippet', '')[:160]}"
        for s in sources[:6]
    )
    prompt = (
        "你是就医导诊助手。只能根据证据说话，禁止确诊、开药、给剂量。"
        "不要使用「你就是」「确诊」「给你开」。"
        "必须在结尾保留不能替代执业医师的声明。"
        "多科室并列，中医证型只作参考不要当诊断。"
        "证据必须对应<用户>里的病名或症状；对不上就说依据不足，禁止改口成头晕或其他无关症状。\n"
        f"意图：{state.get('intent')}\n用户：{state.get('query')}\n证据：\n{evidence or '（无）'}"
    )
    return chat_complete(
        [
            {"role": "system", "content": "只输出给用户的中文回答。"},
            {"role": "user", "content": prompt},
        ],
        max_tokens=500,
    )


def fuse(state: dict[str, Any]) -> str:
    intent = state.get("intent")
    if intent in {"emergency", "refuse", "chitchat"}:
        return template_answer(state)
    if not (state.get("sources") or []):
        return template_answer(state)
    if get_settings().chat_api_key:
        drafted = llm_answer(state)
        if drafted:
            return drafted
    return template_answer(state)
