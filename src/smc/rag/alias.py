"""口语 → 标准名。检索前扩展 query，不在 Cypher 里做模糊。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from config.settings import get_settings


@lru_cache
def load_alias_table(path: Path | None = None) -> dict[str, list[str]]:
    alias_path = path or (get_settings().faq_dir / "aliases.yaml")
    raw = yaml.safe_load(alias_path.read_text(encoding="utf-8")) or {}
    table: dict[str, list[str]] = {}
    for canonical, variants in raw.items():
        if canonical.startswith("#"):
            continue
        names = [str(canonical)]
        if isinstance(variants, list):
            names.extend(str(v) for v in variants)
        table[str(canonical)] = list(dict.fromkeys(names))
    return table


def expand_query(query: str) -> list[str]:
    """返回 query 中命中的标准名及全部变体，供检索与实体链接。"""
    q = query or ""
    found: list[str] = []
    for canonical, variants in load_alias_table().items():
        if any(v and v in q for v in variants):
            found.extend(variants)
            if canonical not in found:
                found.append(canonical)
    return list(dict.fromkeys(found))


def canonical_terms(query: str) -> list[str]:
    q = query or ""
    hits: list[str] = []
    for canonical, variants in load_alias_table().items():
        if any(v and v in q for v in variants):
            hits.append(canonical)
    return hits
