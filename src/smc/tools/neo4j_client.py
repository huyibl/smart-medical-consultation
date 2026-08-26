"""Neo4j 只读客户端。禁止写 Cypher。Label/关系名来自实测 schema。"""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Iterator

from neo4j import GraphDatabase, Driver

from config.settings import Settings, get_settings
from smc.schema import measured_label, measured_rel, name_property

_WRITE = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|FOREACH|LOAD\s+CSV|CALL\s*\{)\b",
    re.IGNORECASE,
)


def assert_readonly(cypher: str) -> None:
    if _WRITE.search(cypher or ""):
        raise PermissionError("图谱只读，拒绝写 Cypher")


class Neo4jClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._driver: Driver | None = None

    def connect(self) -> Driver:
        if self._driver is None:
            if not self.settings.neo4j_password:
                raise RuntimeError("未配置 NEO4J_PASSWORD")
            self._driver = GraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_user, self.settings.neo4j_password),
            )
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def run(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        assert_readonly(cypher)
        driver = self.connect()
        with driver.session(database=self.settings.neo4j_database) as session:
            result = session.run(cypher, **params)
            return [record.data() for record in result]


@contextmanager
def neo4j_client(settings: Settings | None = None) -> Iterator[Neo4jClient]:
    client = Neo4jClient(settings)
    try:
        yield client
    finally:
        client.close()


def probe(client: Neo4jClient) -> dict[str, Any]:
    """验收：节点规模、头痛症状、导诊路径、边方向。"""
    name = name_property()
    disease = measured_label("Disease")
    symptom = measured_label("Symptom")
    has_sym = measured_rel("HAS_SYMPTOM")
    belongs = measured_rel("BELONGS_TO_DEPT")
    parent = measured_rel("DEPT_PARENT")

    counts = client.run(
        "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC"
    )
    headache = client.run(
        f"MATCH (s:`{symptom}`) "
        f"WHERE s.`{name}` = $q OR s.`{name}` CONTAINS $q "
        f"RETURN s.`{name}` AS name LIMIT 10",
        q="头痛",
    )
    triage = client.run(
        f"MATCH (d:`{disease}`)-[:`{has_sym}`]->(s:`{symptom}`) "
        f"WHERE s.`{name}` CONTAINS $q "
        f"OPTIONAL MATCH (d)-[:`{belongs}`]->(dep) "
        f"RETURN d.`{name}` AS disease, s.`{name}` AS symptom, "
        f"labels(dep) AS dept_labels, dep.`{name}` AS department "
        f"LIMIT 20",
        q="头痛",
    )
    belongs_dir = client.run(
        f"MATCH (a)-[:`{belongs}`]->(b) "
        "RETURN labels(a)[0] AS from_label, labels(b)[0] AS to_label, count(*) AS n"
    )
    parent_dir = client.run(
        f"MATCH (a)-[:`{parent}`]->(b) "
        "RETURN labels(a)[0] AS from_label, labels(b)[0] AS to_label, count(*) AS n"
    )
    return {
        "counts": counts,
        "headache_symptoms": headache,
        "triage": triage,
        "rel_所属科室": belongs_dir,
        "rel_属于": parent_dir,
    }


def export_diseases(client: Neo4jClient, limit: int) -> list[dict[str, Any]]:
    name = name_property()
    disease = measured_label("Disease")
    return client.run(
        f"MATCH (d:`{disease}`) "
        f"WHERE d.`{name}` IS NOT NULL "
        f"RETURN d.`{name}` AS name, d.`描述` AS desc, "
        f"d.`病因` AS cause, d.`预防方法` AS prevent "
        f"LIMIT $limit",
        limit=limit,
    )


def export_symptom_bundle(client: Neo4jClient, symptom_name: str) -> list[dict[str, Any]]:
    """只按症状名匹配（精确或包含标准名），不扫疾病描述。"""
    name = name_property()
    disease = measured_label("Disease")
    symptom = measured_label("Symptom")
    has_sym = measured_rel("HAS_SYMPTOM")
    belongs = measured_rel("BELONGS_TO_DEPT")
    return client.run(
        f"MATCH (d:`{disease}`)-[:`{has_sym}`]->(s:`{symptom}`) "
        f"WHERE s.`{name}` = $q OR s.`{name}` CONTAINS $q "
        f"OPTIONAL MATCH (d)-[:`{belongs}`]->(dep) "
        f"RETURN s.`{name}` AS symptom, d.`{name}` AS disease, "
        f"d.`描述` AS desc, dep.`{name}` AS department "
        f"LIMIT 80",
        q=symptom_name,
    )


def export_headache_bundle(client: Neo4jClient) -> list[dict[str, Any]]:
    return export_symptom_bundle(client, "头痛")
