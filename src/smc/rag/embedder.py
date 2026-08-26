"""嵌入：DashScope / 本地 BGE-M3 / dummy（测试）。"""

from __future__ import annotations

from typing import Protocol

from config.settings import Settings, get_settings


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class DashScopeEmbedder:
    def __init__(self, api_key: str, model: str, dimension: int):
        self.api_key = api_key
        self.model = model
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        import dashscope
        from dashscope import TextEmbedding

        dashscope.api_key = self.api_key
        vectors: list[list[float]] = []
        batch_size = 10
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = TextEmbedding.call(
                model=self.model,
                input=batch,
                dimension=self.dimension,
                text_type="document",
            )
            if resp.status_code != 200:
                raise RuntimeError(f"DashScope embedding failed: {resp.message}")
            for item in resp.output["embeddings"]:
                vectors.append(item["embedding"])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class LocalEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.dimension = int(self.model.get_sentence_embedding_dimension())

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.model.encode(text, normalize_embeddings=True).tolist()


class DummyEmbedder:
    """确定性伪向量：测试与无 Key 时仍能按字面重叠拉开距离。"""

    def __init__(self, dimension: int = 64):
        self.dimension = dimension

    def _vec(self, text: str) -> list[float]:
        vec = [0.0] * self.dimension
        blob = text or ""
        for i in range(len(blob) - 1):
            gram = blob[i : i + 2]
            vec[hash(gram) % self.dimension] += 1.0
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


def embedding_dimension(embedder: Embedder) -> int:
    dim = getattr(embedder, "dimension", None)
    if dim:
        return int(dim)
    return len(embedder.embed_query("dim"))


def create_embedder(settings: Settings | None = None) -> Embedder:
    s = settings or get_settings()
    if s.embedding_provider == "dummy":
        return DummyEmbedder(dimension=min(s.embedding_dimension, 64))
    if s.embedding_provider == "local":
        return LocalEmbedder(s.local_embedding_model)
    key = s.dashscope_api_key or s.chat_api_key
    if not key:
        return DummyEmbedder(dimension=min(s.embedding_dimension, 64))
    return DashScopeEmbedder(key, s.embedding_model, s.embedding_dimension)
