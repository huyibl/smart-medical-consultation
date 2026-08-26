"""把 FAQ + 可选图谱文本写入向量库。"""

from __future__ import annotations

from typing import Any

import yaml

from config.settings import Settings, get_settings
from smc.rag.store import VectorStore, open_store


def load_faq_chunks(settings: Settings | None = None) -> list[dict[str, Any]]:
    s = settings or get_settings()
    path = s.faq_dir / "triage.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    chunks: list[dict[str, Any]] = []
    for item in raw.get("items") or []:
        aliases = "、".join(item.get("aliases") or [])
        text = (
            f"{item.get('title')}\n"
            f"标准/口语：{aliases}\n"
            f"建议科室：{item.get('department')}\n"
            f"{item.get('text')}"
        )
        chunks.append(
            {
                "id": f"faq:{item['id']}",
                "text": text,
                "metadata": {
                    "kind": "faq",
                    "title": item.get("title") or "",
                    "department": item.get("department") or "",
                    "source_id": f"faq:{item['id']}",
                    "symptom": (item.get("aliases") or [""])[0],
                    "match_level": "faq",
                },
            }
        )
    return chunks


def chunks_from_diseases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        name = row.get("name") or ""
        if not name:
            continue
        parts = [f"疾病名称：{name}"]
        for key, label in (("desc", "描述"), ("cause", "病因"), ("prevent", "预防方法")):
            val = (row.get(key) or "").strip()
            if val:
                parts.append(f"{label}：{val[:800]}")
        text = "\n".join(parts)
        out.append(
            {
                "id": f"kg:疾病:{name}",
                "text": text,
                "metadata": {
                    "kind": "graph",
                    "title": name,
                    "department": "",
                    "source_id": f"kg:疾病:{name}",
                    "symptom": "",
                    "match_level": "disease_text",
                },
            }
        )
    return out


def chunks_from_headache_bundle(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        symptom = row.get("symptom") or ""
        disease = row.get("disease") or ""
        dept = row.get("department") or ""
        desc = (row.get("desc") or "")[:600]
        text = f"症状：{symptom}\n疾病：{disease}\n建议科室：{dept}\n描述：{desc}"
        sid = f"kg:triage:{disease}:{symptom}:{i}"
        out.append(
            {
                "id": sid,
                "text": text,
                "metadata": {
                    "kind": "graph",
                    "title": disease or symptom,
                    "department": dept,
                    "source_id": sid,
                    "symptom": symptom,
                    "match_level": "exact_symptom",
                },
            }
        )
    return out


def ingest(
    settings: Settings | None = None,
    store: VectorStore | None = None,
    extra_chunks: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    s = settings or get_settings()
    vs = store or open_store(s)
    if hasattr(vs, "reset"):
        vs.reset()
    chunks = load_faq_chunks(s)
    if extra_chunks:
        chunks.extend(extra_chunks)
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for c in chunks:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        uniq.append(c)
    n = vs.add(
        [c["id"] for c in uniq],
        [c["text"] for c in uniq],
        [c["metadata"] for c in uniq],
    )
    return {
        "chunks": n,
        "store_count": vs.count(),
        "rebuilt": bool(getattr(vs, "rebuilt", False)),
    }
