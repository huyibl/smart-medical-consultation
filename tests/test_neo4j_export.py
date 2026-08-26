from smc.tools import neo4j_client as n4j


def test_export_headache_does_not_scan_description():
    source = n4j.export_symptom_bundle.__doc__ or ""
    assert "不扫疾病描述" in source
    # 运行时 Cypher 由 schema 拼出；这里锁查询语义：只允许症状名谓词
    text = open(n4j.__file__, encoding="utf-8").read()
    assert "s.`{name}` = $q OR s.`{name}` CONTAINS $q" in text
    assert "d.`描述` CONTAINS $q" not in text
