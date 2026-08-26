"""实体链接：只从问句和别名出标准名，向量命中不得改写病名。"""

from __future__ import annotations

from smc.rag.alias import canonical_terms, expand_query, load_alias_table
from smc.rag.kg_names import match_kg_names


def link_from_query(query: str) -> list[str]:
    names = list(canonical_terms(query))
    for n in match_kg_names(query):
        if n not in names:
            names.append(n)
    if names:
        return names
    return [v for v in expand_query(query) if v in load_alias_table()][:3]


def link_symptoms(query: str, extra_names: list[str] | None = None) -> list[str]:
    names = link_from_query(query)
    table = load_alias_table()
    q = query or ""
    for raw in extra_names or []:
        if not raw or raw not in q:
            continue
        if raw in table and raw not in names:
            names.append(raw)
        for canonical, variants in table.items():
            if raw in variants and canonical not in names:
                names.append(canonical)
    return names


def link_from_hits(query: str, hits: list[dict]) -> list[str]:
    extras: list[str] = []
    q = query or ""
    for hit in hits:
        meta = hit.get("metadata") or {}
        for key in ("symptom", "title"):
            val = str(meta.get(key) or "")
            if val and val in q:
                extras.append(val)
    return link_symptoms(query, extras)
