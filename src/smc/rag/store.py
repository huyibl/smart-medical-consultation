"""Chroma 持久化向量库（VECTOR_BACKEND=chroma）。FAISS 预留同一接口。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config.settings import Settings, get_settings
from smc.rag.embedder import Embedder, create_embedder, embedding_dimension


class VectorStore:
    rebuilt: bool = False

    def add(self, ids: list[str], texts: list[str], metadatas: list[dict[str, Any]]) -> int:
        raise NotImplementedError

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError


def _peek_collection_dim(col) -> int | None:
    meta = col.metadata or {}
    if meta.get("embedding_dim"):
        return int(meta["embedding_dim"])
    if col.count() == 0:
        return None
    raw = col.get(limit=1, include=["embeddings"])
    embs = raw.get("embeddings")
    if embs is None or len(embs) == 0:
        return None
    first = embs[0]
    return int(len(first))


class ChromaStore(VectorStore):
    def __init__(self, settings: Settings, embedder: Embedder):
        import chromadb

        self.embedder = embedder
        self.rebuilt = False
        self._name = settings.chroma_collection_name
        self._expected_dim = embedding_dimension(embedder)
        persist = Path(settings.chroma_persist_dir)
        persist.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(persist))
        self._col = self._open_collection()

    def _open_collection(self, *, force: bool = False):
        if force:
            self._drop()
        try:
            existing = self._client.get_collection(self._name)
        except Exception:
            existing = None
        if existing is not None:
            stored = _peek_collection_dim(existing)
            if stored is not None and stored != self._expected_dim:
                self._drop()
                existing = None
                self.rebuilt = True
        if existing is None:
            return self._client.get_or_create_collection(
                name=self._name,
                metadata={
                    "hnsw:space": "cosine",
                    "embedding_dim": self._expected_dim,
                },
            )
        return existing

    def _drop(self) -> None:
        try:
            self._client.delete_collection(self._name)
        except Exception:
            pass

    def reset(self) -> None:
        self._col = self._open_collection(force=True)
        self.rebuilt = True

    def add(self, ids: list[str], texts: list[str], metadatas: list[dict[str, Any]]) -> int:
        if not ids:
            return 0
        vectors = self.embedder.embed_documents(texts)
        dim = len(vectors[0]) if vectors else self._expected_dim
        if dim != self._expected_dim:
            self._expected_dim = dim
        try:
            self._col.upsert(
                ids=ids, documents=texts, metadatas=metadatas, embeddings=vectors
            )
        except Exception as exc:
            msg = str(exc).lower()
            if "dimension" not in msg:
                raise
            self._col = self._open_collection(force=True)
            self.rebuilt = True
            self._col.upsert(
                ids=ids, documents=texts, metadatas=metadatas, embeddings=vectors
            )
        return len(ids)

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if self.count() == 0:
            return []
        qv = self.embedder.embed_query(query)
        try:
            raw = self._col.query(
                query_embeddings=[qv], n_results=min(top_k, self.count())
            )
        except Exception as exc:
            if "dimension" not in str(exc).lower():
                raise
            return []
        hits: list[dict[str, Any]] = []
        docs = raw.get("documents") or [[]]
        metas = raw.get("metadatas") or [[]]
        ids = raw.get("ids") or [[]]
        dists = raw.get("distances") or [[]]
        for i, doc in enumerate(docs[0]):
            meta = metas[0][i] if i < len(metas[0]) else {}
            hits.append(
                {
                    "source_id": ids[0][i] if i < len(ids[0]) else "",
                    "text": doc,
                    "metadata": meta or {},
                    "score": 1.0 - float(dists[0][i]) if i < len(dists[0]) else 0.0,
                }
            )
        return hits

    def count(self) -> int:
        return int(self._col.count())


class FaissStore(VectorStore):
    """小规模 IndexFlatIP + jsonl 元数据。向量少时不必 IVF。"""

    def __init__(self, settings: Settings, embedder: Embedder):
        import json

        import numpy as np

        self.embedder = embedder
        self.rebuilt = False
        self._np = np
        self._json = json
        self._expected_dim = embedding_dimension(embedder)
        self.path = Path(settings.faiss_index_path)
        self.meta_path = self.path.with_suffix(".jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ids: list[str] = []
        self._texts: list[str] = []
        self._metas: list[dict[str, Any]] = []
        self._mat = None
        if self.meta_path.exists():
            for line in self.meta_path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self._ids.append(row["id"])
                self._texts.append(row["text"])
                self._metas.append(row.get("metadata") or {})
            npy = self.path.with_suffix(".npy")
            if npy.exists():
                self._mat = np.load(npy)
                if self._mat is not None and self._mat.ndim == 2:
                    if int(self._mat.shape[1]) != self._expected_dim:
                        self._reset()
                        self.rebuilt = True

    def _reset(self) -> None:
        self._ids = []
        self._texts = []
        self._metas = []
        self._mat = None

    def reset(self) -> None:
        self._reset()
        self.rebuilt = True
        npy = self.path.with_suffix(".npy")
        if npy.exists():
            npy.unlink()
        if self.meta_path.exists():
            self.meta_path.unlink()

    def add(self, ids: list[str], texts: list[str], metadatas: list[dict[str, Any]]) -> int:
        if not ids:
            return 0
        vecs = self._np.asarray(self.embedder.embed_documents(texts), dtype="float32")
        if self._mat is not None and int(self._mat.shape[1]) != int(vecs.shape[1]):
            self._reset()
            self.rebuilt = True
        self._ids.extend(ids)
        self._texts.extend(texts)
        self._metas.extend(metadatas)
        self._mat = vecs if self._mat is None else self._np.vstack([self._mat, vecs])
        self._persist()
        return len(ids)

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if self._mat is None or not len(self._ids):
            return []
        q = self._np.asarray(self.embedder.embed_query(query), dtype="float32")
        if int(self._mat.shape[1]) != int(q.shape[0]):
            return []
        mat = self._mat
        denom = (self._np.linalg.norm(mat, axis=1) * self._np.linalg.norm(q)) + 1e-9
        scores = (mat @ q) / denom
        idx = scores.argsort()[::-1][:top_k]
        return [
            {
                "source_id": self._ids[i],
                "text": self._texts[i],
                "metadata": self._metas[i],
                "score": float(scores[i]),
            }
            for i in idx
        ]

    def count(self) -> int:
        return len(self._ids)

    def _persist(self) -> None:
        npy = self.path.with_suffix(".npy")
        self._np.save(npy, self._mat)
        lines = [
            self._json.dumps(
                {"id": i, "text": t, "metadata": m}, ensure_ascii=False
            )
            for i, t, m in zip(self._ids, self._texts, self._metas)
        ]
        self.meta_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def open_store(settings: Settings | None = None, embedder: Embedder | None = None) -> VectorStore:
    s = settings or get_settings()
    emb = embedder or create_embedder(s)
    if s.vector_backend == "faiss":
        return FaissStore(s, emb)
    return ChromaStore(s, emb)
