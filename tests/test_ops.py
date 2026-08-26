import os

import yaml

from config.settings import PROJECT_ROOT, Settings
from smc.observability.log import chat_audit, setup_tracing


def test_compose_default_api_neo4j_is_optional():
    data = yaml.safe_load((PROJECT_ROOT / "deploy" / "docker-compose.yml").read_text(encoding="utf-8"))
    assert "api" in data["services"]
    assert "profiles" not in data["services"]["api"]
    assert data["services"]["neo4j"]["profiles"] == ["neo4j"]
    assert data["services"]["redis"]["profiles"] == ["redis"]
    assert data["services"]["mysql"]["profiles"] == ["mysql"]


def test_dockerfile_exists():
    text = (PROJECT_ROOT / "deploy" / "Dockerfile").read_text(encoding="utf-8")
    assert "frontend/dist" in text
    assert "main.py" in text


def test_chat_audit_fields():
    event = chat_audit(
        {
            "request_id": "abc",
            "intent": "triage",
            "emergency": False,
            "sources": [{"source_id": "kg:肝炎:1"}],
            "department_candidates": ["肝病"],
            "safety": {"blocked": False, "rule_ids": []},
            "trace": [{"elapsed_ms": 12}],
        },
        conversation_id="conv1",
    )
    assert event["event"] == "chat"
    assert event["source_ids"] == ["kg:肝炎:1"]
    assert event["departments"] == ["肝病"]
    assert event["elapsed_ms"] == 12
    assert event["safety_blocked"] is False


def test_setup_tracing_noop_without_key(monkeypatch):
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    setup_tracing(Settings(langsmith_tracing=True, langsmith_api_key=""))
    assert "LANGCHAIN_TRACING_V2" not in os.environ


def test_setup_tracing_sets_env(monkeypatch):
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    setup_tracing(
        Settings(
            langsmith_tracing=True,
            langsmith_api_key="k",
            langsmith_project="smc-test",
        )
    )
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_API_KEY"] == "k"
