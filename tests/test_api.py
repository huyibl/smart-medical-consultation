import json

from fastapi.testclient import TestClient

from config.settings import Settings
from smc.api.app import create_app
from smc.rag.embedder import DummyEmbedder
from smc.rag.ingest import ingest
from smc.rag.store import ChromaStore
from smc.services.history import SqliteHistory


def _settings(tmp_path, **extra) -> Settings:
    return Settings(
        embedding_provider="dummy",
        vector_backend="chroma",
        chroma_persist_dir=tmp_path / "chroma",
        chroma_collection_name="api_test",
        chat_api_key="",
        dashscope_api_key="",
        api_keys=extra.get("api_keys", "test-key"),
        rate_limit_per_minute=extra.get("rate_limit_per_minute", 60),
        sqlite_path=tmp_path / "sessions.db",
        history_max_turns=12,
        frontend_dist=extra.get("frontend_dist", tmp_path / "no-frontend"),
    )


def _client(tmp_path, **extra) -> TestClient:
    settings = _settings(tmp_path, **extra)
    store = ChromaStore(settings, DummyEmbedder())
    hist = SqliteHistory(settings.sqlite_path, settings.history_max_turns)
    return TestClient(create_app(settings=settings, store=store, history=hist))


def _events(response) -> list[dict]:
    out = []
    for block in response.text.split("\n\n"):
        line = block.strip()
        if line.startswith("data:"):
            out.append(json.loads(line[5:].strip()))
    return out


def test_health_no_key(tmp_path):
    client = _client(tmp_path)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_chat_missing_key_401(tmp_path):
    client = _client(tmp_path)
    r = client.post("/v1/chat", json={"query": "你好"})
    assert r.status_code == 401
    assert r.json()["code"] == "unauthorized"


def test_chat_wrong_key_401(tmp_path):
    client = _client(tmp_path)
    r = client.post(
        "/v1/chat",
        json={"query": "你好"},
        headers={"X-API-Key": "nope"},
    )
    assert r.status_code == 401


def test_chat_bearer_and_sse_types(tmp_path):
    client = _client(tmp_path)
    r = client.post(
        "/v1/chat",
        json={"query": "你好"},
        headers={"Authorization": "Bearer test-key"},
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    events = _events(r)
    types = [e["type"] for e in events]
    assert events[0]["type"] == "trace"
    assert events[0].get("status") == "started"
    assert "trace" in types
    assert "token" in types
    assert types[-2] == "safety"
    assert types[-1] == "done"
    assert set(types) <= {"trace", "token", "sources", "safety", "done", "error"}
    done = events[-1]
    assert done["intent"] == "chitchat"
    assert done["conversation_id"]
    assert done["request_id"]
    text = "".join(e["text"] for e in events if e["type"] == "token")
    assert "执业医师" in text or "导诊" in text


def test_chat_emergency_sse(tmp_path):
    client = _client(tmp_path)
    r = client.post(
        "/v1/chat",
        json={"query": "突然胸口剧痛还出冷汗"},
        headers={"X-API-Key": "test-key"},
    )
    assert r.status_code == 200
    events = _events(r)
    safety = next(e for e in events if e["type"] == "safety")
    done = next(e for e in events if e["type"] == "done")
    assert safety["emergency"] is True
    assert safety["blocked"] is True
    assert done["intent"] == "emergency"
    text = "".join(e["text"] for e in events if e["type"] == "token")
    assert "急救" in text and "急诊" in text


def test_chat_rate_limit_429(tmp_path):
    client = _client(tmp_path, rate_limit_per_minute=1)
    headers = {"X-API-Key": "test-key"}
    ok = client.post("/v1/chat", json={"query": "你好"}, headers=headers)
    assert ok.status_code == 200
    limited = client.post("/v1/chat", json={"query": "你好"}, headers=headers)
    assert limited.status_code == 429
    assert limited.json()["code"] == "rate_limited"


def test_history_survives_reopen(tmp_path):
    settings = _settings(tmp_path)
    store = ChromaStore(settings, DummyEmbedder())
    hist = SqliteHistory(settings.sqlite_path, settings.history_max_turns)
    client = TestClient(create_app(settings=settings, store=store, history=hist))
    headers = {"X-API-Key": "test-key"}
    first = _events(client.post("/v1/chat", json={"query": "你好"}, headers=headers))
    cid = first[-1]["conversation_id"]
    client.post(
        "/v1/chat",
        json={"query": "谢谢", "conversation_id": cid},
        headers=headers,
    )
    # 模拟重启：新 History 实例读同一文件
    hist2 = SqliteHistory(settings.sqlite_path, settings.history_max_turns)
    client2 = TestClient(create_app(settings=settings, store=store, history=hist2))
    got = client2.get(f"/v1/conversations/{cid}", headers=headers)
    assert got.status_code == 200
    roles = [m["role"] for m in got.json()["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    asst = [m for m in got.json()["messages"] if m["role"] == "assistant"][0]
    assert asst.get("intent") == "chitchat"
    assert "elapsed_ms" in asst
    listed = client2.get("/v1/conversations", headers=headers)
    assert listed.status_code == 200
    assert any(i["conversation_id"] == cid for i in listed.json()["items"])


def test_invalid_conversation_id(tmp_path):
    client = _client(tmp_path)
    r = client.post(
        "/v1/chat",
        json={"query": "你好", "conversation_id": "bad"},
        headers={"X-API-Key": "test-key"},
    )
    assert r.status_code == 400


def test_chat_triage_has_sources(tmp_path):
    settings = _settings(tmp_path)
    store = ChromaStore(settings, DummyEmbedder())
    ingest(settings, store=store)
    hist = SqliteHistory(settings.sqlite_path, settings.history_max_turns)
    client = TestClient(create_app(settings=settings, store=store, history=hist))
    r = client.post(
        "/v1/chat",
        json={"query": "最近老是头疼该挂哪科"},
        headers={"X-API-Key": "test-key"},
    )
    assert r.status_code == 200
    events = _events(r)
    types = [e["type"] for e in events]
    assert "sources" in types
    assert events[-1]["intent"] == "triage"
    text = "".join(e["text"] for e in events if e["type"] == "token")
    assert "不能替代" in text or "执业医师" in text


def test_serves_frontend_index(tmp_path):
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><title>智慧问诊</title><p>本系统不能替代专业诊疗</p>",
        encoding="utf-8",
    )
    (assets / "app.js").write_text("window.__SMC=1", encoding="utf-8")
    client = _client(tmp_path, frontend_dist=dist)
    home = client.get("/")
    assert home.status_code == 200
    assert "不能替代专业诊疗" in home.text
    js = client.get("/assets/app.js")
    assert js.status_code == 200
    assert "window.__SMC" in js.text
    assert client.get("/health").status_code == 200
    assert client.post("/v1/chat", json={"query": "你好"}).status_code == 401


def test_frontend_hint_when_unbuilt(tmp_path):
    client = _client(tmp_path)
    home = client.get("/")
    assert home.status_code == 200
    assert "npm run build" in home.text
