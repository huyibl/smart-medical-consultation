from config.settings import Settings
from smc.agents.intent import detect_intent, rule_intent
from smc.rag.embedder import DummyEmbedder
from smc.rag.ingest import ingest
from smc.rag.store import ChromaStore
from smc.services.ask import ask, ask_events


def test_rule_intents():
    assert rule_intent("突然胸口剧痛，还出冷汗") == "emergency"
    assert rule_intent("给我开点阿莫西林") == "refuse"
    assert rule_intent("你好") == "chitchat"
    assert detect_intent("最近老是头疼该挂哪科", allow_llm=False) == "triage"
    assert rule_intent("阿司匹林一般用在什么情况，我能自己吃吗") == "medication_info"
    assert rule_intent("荨麻疹应该去什么科室") == "triage"
    assert rule_intent("肝炎应该挂哪科") == "triage"
    assert rule_intent("肝炎是什么") == "knowledge"


def test_ask_emergency_skips_retrieve():
    result = ask("突然胸口剧痛，还出冷汗")
    assert result["intent"] == "emergency"
    assert result["emergency"] is True
    assert "急救" in result["answer"]
    assert "急诊" in result["answer"]
    nodes = [t["node"] for t in result["trace"]]
    assert not any(str(n).startswith("retrieve") for n in nodes)
    assert result["safety"]["blocked"] is True


def test_ask_refuse_no_prescription():
    result = ask("给我开点阿莫西林，嗓子疼")
    assert result["intent"] == "refuse"
    assert "给你开" not in result["answer"]
    assert "不能替代" in result["answer"] or "执业医师" in result["answer"]


def test_ask_triage_headache(tmp_path):
    settings = Settings(
        embedding_provider="dummy",
        vector_backend="chroma",
        chroma_persist_dir=tmp_path / "chroma",
        chroma_collection_name="agent_faq",
        chat_api_key="",
        dashscope_api_key="",
    )
    store = ChromaStore(settings, DummyEmbedder())
    ingest(settings, store=store)
    result = ask("最近老是头疼该挂哪科", store=store)
    assert result["intent"] == "triage"
    nodes = [t["node"] for t in result["trace"]]
    assert "retrieve_triage" in nodes
    assert "retrieve_hybrid" not in nodes
    assert "神经内科" in result["answer"]
    assert result.get("sources")
    assert "不能替代" in result["answer"] or "执业医师" in result["answer"]


def test_ask_hepatitis_not_dizziness(tmp_path):
    settings = Settings(
        embedding_provider="dummy",
        vector_backend="chroma",
        chroma_persist_dir=tmp_path / "chroma",
        chroma_collection_name="agent_hep",
        chat_api_key="",
        dashscope_api_key="",
    )
    store = ChromaStore(settings, DummyEmbedder())
    ingest(settings, store=store)
    result = ask("肝炎应该挂哪科", store=store)
    assert result["intent"] == "triage"
    answer = result.get("answer") or ""
    assert "仅能提供与“头晕”" not in answer
    assert "围绕“头晕”" not in answer
    snippets = " ".join(s.get("snippet") or "" for s in result.get("sources") or [])
    if not (result.get("sources") or []):
        assert "没有匹配" in answer or "依据不足" in answer
    else:
        assert "肝炎" in snippets or "肝炎" in answer or "消化" in answer or "感染" in answer


def test_ask_medication_info_route(tmp_path):
    settings = Settings(
        embedding_provider="dummy",
        vector_backend="chroma",
        chroma_persist_dir=tmp_path / "chroma",
        chroma_collection_name="agent_med",
        chat_api_key="",
        dashscope_api_key="",
    )
    store = ChromaStore(settings, DummyEmbedder())
    ingest(settings, store=store)
    result = ask("阿司匹林一般用在什么情况", store=store)
    assert result["intent"] == "medication_info"
    nodes = [t["node"] for t in result["trace"]]
    assert "retrieve_med" in nodes
    assert "retrieve_triage" not in nodes
    assert "遵医嘱" in result["answer"] or "药师" in result["answer"]
    assert "给你开" not in result["answer"]


def test_ask_events_contract_types(tmp_path):
    events = list(ask_events("你好"))
    types = [e["type"] for e in events]
    assert "trace" in types
    assert "token" in types
    assert types[-2] == "safety"
    assert types[-1] == "done"
