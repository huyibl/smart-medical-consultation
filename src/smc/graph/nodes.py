"""按意图分叉检索。导诊不靠向量给科室排名。"""

from __future__ import annotations

from typing import Any

from smc.agents.fuse import fuse
from smc.agents.intent import detect_intent, extract_entities
from smc.graph.trace import append_trace, now_ms
from smc.rag.link import link_from_query
from smc.rag.retriever import search
from smc.safety.rules import classify_input, emergency_reply, review_output
from smc.tools.graph_query import (
    query_diseases,
    query_drugs,
    query_triage_by_diseases,
    query_triage_by_symptoms,
)

_STORE = None


def set_store(store) -> None:
    global _STORE
    _STORE = store


def _sources_from_hits(hits: list[dict[str, Any]]) -> list[dict[str, str]]:
    out = []
    for h in hits:
        meta = h.get("metadata") or {}
        out.append(
            {
                "source_id": str(h.get("source_id") or meta.get("source_id") or ""),
                "kind": str(meta.get("kind") or "vector"),
                "title": str(meta.get("title") or ""),
                "snippet": str(h.get("text") or "")[:240],
            }
        )
    return out


def _graph_triage_sources(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out = []
    for i, row in enumerate(rows[:8]):
        disease = str(row.get("disease") or "")
        symptom = str(row.get("symptom") or "")
        dept = str(row.get("department") or "")
        if symptom and symptom != disease:
            snippet = f"症状{symptom} → 疾病{disease} → 科室{dept}"
        else:
            snippet = f"疾病{disease} → 科室{dept}"
        out.append(
            {
                "source_id": f"kg:{disease}:{symptom}:{i}",
                "kind": "graph",
                "title": disease or symptom,
                "snippet": snippet,
            }
        )
    return out


def _faq_matches(hit: dict[str, Any], query: str, linked: list[str]) -> bool:
    meta = hit.get("metadata") or {}
    blob = f"{meta.get('title') or ''} {meta.get('symptom') or ''} {hit.get('text') or ''}"
    keys = list(linked) + [query]
    return any(k and k in blob for k in keys if k and len(k) >= 2)


def _collect_depts(hits: list[dict[str, Any]], graph_rows: list[dict[str, Any]]) -> list[str]:
    depts: list[str] = []
    for h in hits:
        d = (h.get("metadata") or {}).get("department")
        if d:
            depts.append(str(d))
    for row in graph_rows:
        d = row.get("department")
        if d:
            depts.append(str(d))
    seen: list[str] = []
    for d in depts:
        if d and d not in seen:
            seen.append(d)
    return seen


def emergency_gate_node(state: dict[str, Any]) -> dict[str, Any]:
    t0 = now_ms()
    query = state.get("query") or ""
    emergency = classify_input(query) == "emergency"
    return {
        "emergency": emergency,
        "intent": "emergency" if emergency else state.get("intent"),
        "skip_retrieve": emergency,
        "trace": append_trace(state, "emergency_gate", t0, str(emergency)),
    }


def intent_node(state: dict[str, Any]) -> dict[str, Any]:
    t0 = now_ms()
    if state.get("emergency"):
        return {"intent": "emergency", "skip_retrieve": True}
    query = state.get("query") or ""
    intent = detect_intent(query, allow_llm=True)
    skip = intent in {"chitchat", "refuse", "emergency"}
    return {
        "intent": intent,
        "entities": extract_entities(query),
        "skip_retrieve": skip,
        "retrieve_mode": intent,
        "trace": append_trace(state, "intent", t0, intent),
    }


def retrieve_triage_node(state: dict[str, Any]) -> dict[str, Any]:
    t0 = now_ms()
    query = state.get("query") or ""
    linked = link_from_query(query)
    symptom_rows = query_triage_by_symptoms(linked)
    disease_rows = query_triage_by_diseases(linked, fuzzy=not bool(symptom_rows))
    rows = symptom_rows + disease_rows
    hits = search(query, store=_STORE, top_k=5)
    faq_hits = [
        h
        for h in hits
        if (h.get("metadata") or {}).get("kind") == "faq" and _faq_matches(h, query, linked)
    ]
    sources = _sources_from_hits(faq_hits) + _graph_triage_sources(rows)
    return {
        "entities": {**(state.get("entities") or {}), "symptoms": linked, "diseases": linked},
        "retrieval": {"vector": faq_hits, "graph": rows},
        "sources": sources,
        "trace": append_trace(state, "retrieve_triage", t0, f"link={linked} n={len(sources)}"),
    }


def retrieve_hybrid_node(state: dict[str, Any]) -> dict[str, Any]:
    t0 = now_ms()
    query = state.get("query") or ""
    linked = link_from_query(query)
    hits = search(query, store=_STORE, top_k=5)
    if linked:
        hits = [h for h in hits if _faq_matches(h, query, linked)]
    else:
        hits = []
    symptom_rows = query_triage_by_symptoms(linked)
    graph_rows = symptom_rows + query_triage_by_diseases(linked, fuzzy=not bool(symptom_rows))
    disease_rows = query_diseases(linked)
    sources = _graph_triage_sources(graph_rows)
    for i, row in enumerate(disease_rows[:4]):
        sources.append(
            {
                "source_id": f"kg:疾病:{row.get('disease')}:{i}",
                "kind": "graph",
                "title": str(row.get("disease") or ""),
                "snippet": str(row.get("desc") or "")[:200],
            }
        )
    sources.extend(_sources_from_hits(hits))
    return {
        "retrieval": {"vector": hits, "graph": graph_rows + disease_rows},
        "sources": sources,
        "trace": append_trace(state, "retrieve_hybrid", t0, f"link={linked} n={len(sources)}"),
    }


def retrieve_med_node(state: dict[str, Any]) -> dict[str, Any]:
    t0 = now_ms()
    query = state.get("query") or ""
    if classify_input(query) == "refuse":
        return {
            "intent": "refuse",
            "retrieval": {"vector": [], "graph": []},
            "sources": [],
            "trace": append_trace(state, "retrieve_med", t0, "refuse"),
        }
    linked = link_from_query(query)
    hits = search(query, store=_STORE, top_k=5)
    if linked:
        hits = [h for h in hits if _faq_matches(h, query, linked)]
    else:
        hits = []
    drugs = query_drugs(linked)
    sources = _sources_from_hits(hits)
    for i, row in enumerate(drugs[:6]):
        sources.append(
            {
                "source_id": f"kg:药物:{row.get('drug')}:{i}",
                "kind": "graph",
                "title": str(row.get("drug") or ""),
                "snippet": f"关联疾病：{row.get('disease') or ''}",
            }
        )
    return {
        "retrieval": {"vector": hits, "graph": drugs},
        "sources": sources,
        "trace": append_trace(state, "retrieve_med", t0, f"n={len(sources)}"),
    }


def dept_or_med_or_knowledge_node(state: dict[str, Any]) -> dict[str, Any]:
    t0 = now_ms()
    hits = (state.get("retrieval") or {}).get("vector") or []
    graph_rows = (state.get("retrieval") or {}).get("graph") or []
    depts = _collect_depts(hits, graph_rows)
    return {
        "department_candidates": depts,
        "trace": append_trace(state, "dept_or_med_or_knowledge", t0, "、".join(depts[:4])),
    }


def fuse_stream_node(state: dict[str, Any]) -> dict[str, Any]:
    t0 = now_ms()
    text = fuse(state)
    return {
        "generator_output": text,
        "trace": append_trace(state, "fuse_stream", t0, text[:80]),
    }


def safety_rewrite_node(state: dict[str, Any]) -> dict[str, Any]:
    t0 = now_ms()
    if state.get("emergency") or state.get("intent") == "emergency":
        answer = emergency_reply()
        safety = {"blocked": True, "rewritten": True, "rule_ids": ["R-EMERGENCY-RECALL"]}
        return {
            "answer": answer,
            "generator_output": answer,
            "safety": safety,
            "trace": append_trace(state, "safety_rewrite", t0, "emergency"),
        }
    draft = state.get("generator_output") or fuse(state)
    intent = state.get("intent") or "triage"
    review = review_output(
        draft,
        intent=intent,
        medication=intent == "medication_info",
    )
    rewritten = False
    answer = draft
    if not review["ok"]:
        from smc.agents.fuse import template_answer

        answer = template_answer({**state, "intent": intent})
        rewritten = True
        review = review_output(
            answer,
            intent=intent,
            medication=intent == "medication_info",
        )
    safety = {
        "blocked": not review["ok"],
        "rewritten": rewritten,
        "rule_ids": review["rule_ids"],
    }
    return {
        "answer": answer,
        "safety": safety,
        "trace": append_trace(state, "safety_rewrite", t0, ",".join(review["rule_ids"]) or "ok"),
    }
