"""别名扩展 + 向量检索 + 规则加权。验收：头疼能命中含头痛的 chunk。"""

from __future__ import annotations

from typing import Any

from config.settings import Settings, get_settings
from smc.rag.alias import canonical_terms, expand_query
from smc.rag.store import VectorStore, open_store

FAQ_BOOST = 0.18
EXACT_SYMPTOM_BOOST = 0.16
TITLE_SYMPTOM_BOOST = 0.06
BODY_ONLY_PENALTY = 0.08


def _rerank(hits: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    aliases = expand_query(query)
    canonicals = canonical_terms(query)
    keys = list(dict.fromkeys([*canonicals, *aliases]))

    ranked: list[dict[str, Any]] = []
    for hit in hits:
        meta = hit.get("metadata") or {}
        kind = meta.get("kind") or ""
        symptom = str(meta.get("symptom") or "")
        match_level = str(meta.get("match_level") or "")
        text = hit.get("text") or ""
        header = text.split("描述：", 1)[0]
        boost = 0.0
        if kind == "faq":
            boost += FAQ_BOOST
        exact = bool(canonicals) and any(
            symptom == c or symptom.startswith(c) for c in canonicals
        )
        if exact or match_level == "exact_symptom":
            boost += EXACT_SYMPTOM_BOOST
        elif any(k and k in header for k in keys):
            boost += TITLE_SYMPTOM_BOOST
        elif match_level == "disease_text" or (
            keys and any(k in text for k in keys) and not exact
        ):
            boost -= BODY_ONLY_PENALTY
        hit = dict(hit)
        hit["rank_score"] = float(hit.get("score") or 0.0) + boost
        ranked.append(hit)
    ranked.sort(key=lambda h: h["rank_score"], reverse=True)
    return ranked


def search(
    query: str,
    settings: Settings | None = None,
    store: VectorStore | None = None,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    s = settings or get_settings()
    vs = store or open_store(s)
    k = top_k or s.retrieval_top_k
    aliases = expand_query(query)
    expanded = query if not aliases else f"{query} {' '.join(aliases)}"
    pool = vs.search(expanded, max(k * 4, 12))
    hits = _rerank(pool, query)[:k]
    canonicals = canonical_terms(query)
    for hit in hits:
        text = hit.get("text") or ""
        meta = hit.get("metadata") or {}
        hit["matched_alias"] = any(a in text for a in aliases) if aliases else False
        hit["contains_头痛"] = "头痛" in text or meta.get("symptom") == "头痛"
        hit["symptom_hit"] = bool(
            canonicals
            and any(
                str(meta.get("symptom") or "") == c
                or str(meta.get("symptom") or "").startswith(c)
                for c in canonicals
            )
        )
    return hits


def headache_alias_ok(hits: list[dict[str, Any]]) -> bool:
    return any(
        h.get("contains_头痛")
        or "头痛" in (h.get("text") or "")
        or (h.get("metadata") or {}).get("kind") == "faq"
        for h in hits
    )
