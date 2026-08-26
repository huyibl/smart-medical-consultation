"""只读模板 Cypher。失败返回空列表。"""

from __future__ import annotations

from typing import Any

from smc.schema import measured_label, measured_rel, name_property


def _client():
    from smc.tools.neo4j_client import neo4j_client

    return neo4j_client()


def export_entity_names() -> tuple[set[str], set[str]]:
    """疾病名、症状名。失败返回空集合。"""
    prop = name_property()
    disease = measured_label("Disease")
    symptom = measured_label("Symptom")
    try:
        with _client() as client:
            d_rows = client.run(f"MATCH (d:`{disease}`) RETURN d.`{prop}` AS name")
            s_rows = client.run(f"MATCH (s:`{symptom}`) RETURN s.`{prop}` AS name")
    except Exception:
        return set(), set()
    diseases = {str(r["name"]) for r in d_rows if r.get("name")}
    symptoms = {str(r["name"]) for r in s_rows if r.get("name")}
    return diseases, symptoms


def query_triage_by_diseases(
    disease_names: list[str], *, fuzzy: bool = True
) -> list[dict[str, Any]]:
    """按疾病名查科室。先精确；仅当没有症状命中时才 CONTAINS（肝炎→乙型肝炎）。"""
    names = [n for n in disease_names if n and len(n) >= 2]
    if not names:
        return []
    prop = name_property()
    disease = measured_label("Disease")
    belongs = measured_rel("BELONGS_TO_DEPT")
    exact = (
        f"MATCH (d:`{disease}`) WHERE d.`{prop}` IN $names "
        f"OPTIONAL MATCH (d)-[:`{belongs}`]->(dep) "
        f"RETURN d.`{prop}` AS disease, d.`{prop}` AS symptom, "
        f"dep.`{prop}` AS department LIMIT 20"
    )
    fuzzy_cypher = (
        f"MATCH (d:`{disease}`) WHERE any(n IN $names WHERE d.`{prop}` CONTAINS n) "
        f"OPTIONAL MATCH (d)-[:`{belongs}`]->(dep) "
        f"RETURN d.`{prop}` AS disease, d.`{prop}` AS symptom, "
        f"dep.`{prop}` AS department LIMIT 15"
    )
    try:
        with _client() as client:
            rows = client.run(exact, names=names)
            if rows or not fuzzy:
                return rows
            return client.run(fuzzy_cypher, names=names)
    except Exception:
        return []


def query_triage_by_symptoms(symptom_names: list[str]) -> list[dict[str, Any]]:
    """标准名精确匹配，不用 CONTAINS，避免神经性头痛等噪声。"""
    names = [n for n in symptom_names if n]
    if not names:
        return []
    prop = name_property()
    disease = measured_label("Disease")
    symptom = measured_label("Symptom")
    has_sym = measured_rel("HAS_SYMPTOM")
    belongs = measured_rel("BELONGS_TO_DEPT")
    cypher = (
        f"MATCH (s:`{symptom}`) WHERE s.`{prop}` IN $names "
        f"MATCH (d:`{disease}`)-[:`{has_sym}`]->(s) "
        f"OPTIONAL MATCH (d)-[:`{belongs}`]->(dep) "
        f"RETURN s.`{prop}` AS symptom, d.`{prop}` AS disease, "
        f"dep.`{prop}` AS department LIMIT 20"
    )
    try:
        with _client() as client:
            return client.run(cypher, names=names)
    except Exception:
        return []


def query_drugs(names: list[str]) -> list[dict[str, Any]]:
    names = [n for n in names if n]
    if not names:
        return []
    prop = name_property()
    disease = measured_label("Disease")
    drug = measured_label("Drug")
    common = measured_rel("COMMON_DRUG")
    rated = measured_rel("RATED_DRUG")
    cypher = (
        f"MATCH (x) WHERE x.`{prop}` IN $names "
        f"OPTIONAL MATCH (x)-[:`{common}`|`{rated}`]->(drug:`{drug}`) "
        f"OPTIONAL MATCH (d:`{disease}`)-[:`{common}`|`{rated}`]->(x) "
        f"RETURN coalesce(drug.`{prop}`, x.`{prop}`) AS drug, "
        f"d.`{prop}` AS disease LIMIT 20"
    )
    try:
        with _client() as client:
            return client.run(cypher, names=names)
    except Exception:
        return []


def query_diseases(names: list[str]) -> list[dict[str, Any]]:
    names = [n for n in names if n]
    if not names:
        return []
    prop = name_property()
    disease = measured_label("Disease")
    check = measured_label("Check")
    need = measured_rel("NEED_CHECK")
    exact = (
        f"MATCH (d:`{disease}`) WHERE d.`{prop}` IN $names "
        f"OPTIONAL MATCH (d)-[:`{need}`]->(c:`{check}`) "
        f"RETURN d.`{prop}` AS disease, d.`描述` AS desc, "
        f"collect(DISTINCT c.`{prop}`) AS checks LIMIT 10"
    )
    fuzzy = (
        f"MATCH (d:`{disease}`) WHERE any(n IN $names WHERE d.`{prop}` CONTAINS n) "
        f"OPTIONAL MATCH (d)-[:`{need}`]->(c:`{check}`) "
        f"RETURN d.`{prop}` AS disease, d.`描述` AS desc, "
        f"collect(DISTINCT c.`{prop}`) AS checks LIMIT 10"
    )
    try:
        with _client() as client:
            rows = client.run(exact, names=names)
            if rows:
                return rows
            return client.run(fuzzy, names=names)
    except Exception:
        return []
