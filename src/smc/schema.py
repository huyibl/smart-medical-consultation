"""加载实测图谱 schema。tools 只读 measured 中文名。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from config.settings import PROJECT_ROOT, get_settings


@lru_cache
def load_kg_schema(path: Path | None = None) -> dict[str, Any]:
    schema_path = path or get_settings().kg_schema_path
    if not schema_path.is_absolute():
        schema_path = PROJECT_ROOT / schema_path
    data = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"非法 kg schema: {schema_path}")
    return data


def measured_label(logical: str) -> str:
    node = load_kg_schema()["node_labels"][logical]
    label = node.get("measured") or node.get("assumed")
    if not label:
        raise KeyError(f"schema 缺少 Label: {logical}")
    return str(label)


def measured_rel(logical: str) -> str:
    rel = load_kg_schema()["relationship_types"][logical]
    name = rel.get("measured") or rel.get("assumed")
    if not name:
        raise KeyError(f"schema 缺少关系: {logical}")
    return str(name)


def name_property() -> str:
    return str(load_kg_schema().get("name_property") or "名称")
