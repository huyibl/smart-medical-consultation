import pytest

from smc.tools.neo4j_client import assert_readonly


def test_read_ok():
    assert_readonly("MATCH (n:疾病) RETURN n.名称 LIMIT 1")


@pytest.mark.parametrize(
    "q",
    [
        "CREATE (n:疾病 {名称:'x'})",
        "MATCH (n) SET n.名称='x'",
        "MATCH (n) DELETE n",
        "MERGE (n:疾病 {名称:'x'})",
    ],
)
def test_write_rejected(q):
    with pytest.raises(PermissionError):
        assert_readonly(q)
