from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from config.settings import Settings
from smc.rag.alias import canonical_terms, expand_query
from smc.rag.embedder import DummyEmbedder
from smc.rag.ingest import chunks_from_headache_bundle, ingest
from smc.rag.retriever import headache_alias_ok, search
from smc.rag.store import ChromaStore


def test_alias_头疼_to_头痛():
    assert "头痛" in expand_query("我最近老是头疼")
    assert "高血压" in canonical_terms("血压高好久了")


def test_search_头疼_hits_头痛(tmp_path):
    settings = Settings(
        embedding_provider="dummy",
        vector_backend="chroma",
        chroma_persist_dir=tmp_path / "chroma",
        chroma_collection_name="t_faq",
    )
    store = ChromaStore(settings, DummyEmbedder())
    ingest(settings, store=store)
    hits = search("最近老是头疼该挂哪科", settings=settings, store=store, top_k=5)
    assert hits
    assert headache_alias_ok(hits)
    assert any("神经内科" in (h.get("text") or "") for h in hits)


def test_chroma_rebuilds_on_dimension_mismatch(tmp_path):
    settings = Settings(
        embedding_provider="dummy",
        vector_backend="chroma",
        chroma_persist_dir=tmp_path / "chroma",
        chroma_collection_name="dim_mix",
    )
    old = ChromaStore(settings, DummyEmbedder(64))
    old.add(
        ["faq:old"],
        ["旧索引 64 维"],
        [{"kind": "faq", "title": "old", "department": "", "source_id": "faq:old"}],
    )
    assert old.count() == 1

    new = ChromaStore(settings, DummyEmbedder(32))
    assert new.rebuilt is True
    n = new.add(
        ["faq:new"],
        ["头痛 头疼 神经内科"],
        [{"kind": "faq", "title": "new", "department": "神经内科", "source_id": "faq:new"}],
    )
    assert n == 1
    assert new.count() == 1


def test_graph_chunk_has_no_forced_headache_suffix():
    chunks = chunks_from_headache_bundle(
        [
            {
                "symptom": "乏力",
                "disease": "军团病",
                "department": "呼吸内科",
                "desc": "可有发热、头痛、肌痛。",
            }
        ]
    )
    assert chunks
    assert "规范名头痛可能由口语头疼触发" not in chunks[0]["text"]
    assert chunks[0]["metadata"]["symptom"] == "乏力"


def test_faq_outranks_body_only_mention(tmp_path):
    settings = Settings(
        embedding_provider="dummy",
        vector_backend="chroma",
        chroma_persist_dir=tmp_path / "chroma",
        chroma_collection_name="rank",
    )
    store = ChromaStore(settings, DummyEmbedder())
    ingest(settings, store=store)
    store.add(
        ["kg:triage:军团病:乏力:0"],
        ["症状：乏力\n疾病：军团病\n建议科室：呼吸内科\n描述：可有发热、头痛、肌痛。"],
        [
            {
                "kind": "graph",
                "title": "军团病",
                "department": "呼吸内科",
                "source_id": "kg:triage:军团病:乏力:0",
                "symptom": "乏力",
                "match_level": "disease_text",
            }
        ],
    )
    hits = search("最近老是头疼该挂哪科", settings=settings, store=store, top_k=5)
    assert hits
    assert hits[0]["metadata"]["kind"] == "faq"
    assert hits[0]["metadata"].get("source_id") != "kg:triage:军团病:乏力:0"
    assert any("神经内科" in (h.get("text") or "") for h in hits)
