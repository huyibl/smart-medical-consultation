from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from smc.schema import load_kg_schema, measured_label, measured_rel, name_property


def test_measured_labels_are_chinese():
    assert measured_label("Disease") == "疾病"
    assert measured_label("Symptom") == "症状"
    assert measured_label("Department") == "二级科室"
    assert measured_rel("HAS_SYMPTOM") == "症状"
    assert measured_rel("BELONGS_TO_DEPT") == "所属科室"
    assert name_property() == "名称"


def test_schema_status_is_measured():
    data = load_kg_schema()
    assert data["source"]["measured_node_count"] == 62196
    assert "pending_dump" not in str(data.get("status"))
