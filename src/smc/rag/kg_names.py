"""图谱标准名缓存：问句最长匹配，不靠向量猜病名。"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from config.settings import get_settings

MIN_LEN = 2

_LOCK = threading.Lock()
_CACHE: dict[str, set[str]] | None = None


def cache_path() -> Path:
    return Path(get_settings().chroma_persist_dir).parent / "kg_names.json"


def _normalize(names: list[str]) -> set[str]:
    return {n.strip() for n in names if n and len(n.strip()) >= MIN_LEN}


def load_name_sets() -> tuple[set[str], set[str]]:
    global _CACHE
    with _LOCK:
        if _CACHE is not None:
            return _CACHE["diseases"], _CACHE["symptoms"]
        data = {"diseases": set(), "symptoms": set()}
        path = cache_path()
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            data["diseases"] = _normalize(list(raw.get("diseases") or []))
            data["symptoms"] = _normalize(list(raw.get("symptoms") or []))
        _CACHE = data
        return data["diseases"], data["symptoms"]


def reset_name_cache() -> None:
    global _CACHE
    with _LOCK:
        _CACHE = None


def refresh_name_cache() -> dict[str, int]:
    """从 Neo4j 拉疾病/症状名。失败则保留旧缓存。"""
    from smc.tools.graph_query import export_entity_names

    diseases, symptoms = export_entity_names()
    if not diseases and not symptoms:
        d, s = load_name_sets()
        return {"diseases": len(d), "symptoms": len(s), "refreshed": 0}
    payload = {"diseases": sorted(diseases), "symptoms": sorted(symptoms)}
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    global _CACHE
    with _LOCK:
        _CACHE = {"diseases": set(diseases), "symptoms": set(symptoms)}
    return {"diseases": len(diseases), "symptoms": len(symptoms), "refreshed": 1}


def match_kg_names(query: str) -> list[str]:
    q = query or ""
    if not q:
        return []
    diseases, symptoms = load_name_sets()
    return longest_match(q, diseases | symptoms)


def longest_match(query: str, names: set[str]) -> list[str]:
    q = query or ""
    candidates = [n for n in names if n and len(n) >= MIN_LEN and n in q]
    candidates.sort(key=len, reverse=True)
    used = [False] * len(q)
    selected: list[str] = []
    for name in candidates:
        start = q.find(name)
        while start >= 0:
            if not any(used[start : start + len(name)]):
                for i in range(start, start + len(name)):
                    used[i] = True
                selected.append(name)
                break
            start = q.find(name, start + 1)
    return selected
