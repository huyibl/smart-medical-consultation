"""从 .env / 环境变量加载配置。改这些键不需要改业务代码。"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """智慧问诊数据层与后续在线链路的中央配置。"""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    chat_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="CHAT_BASE_URL",
    )
    chat_api_key: str = Field(default="", alias="CHAT_API_KEY")
    chat_model: str = Field(default="qwen-plus", alias="CHAT_MODEL")

    extract_base_url: str = Field(default="", alias="EXTRACT_BASE_URL")
    extract_api_key: str = Field(default="", alias="EXTRACT_API_KEY")
    extract_model: str = Field(default="qwen-plus", alias="EXTRACT_MODEL")

    dashscope_api_key: str = Field(default="", alias="DASHSCOPE_API_KEY")
    embedding_provider: Literal["dashscope", "local", "dummy"] = Field(
        default="dashscope", alias="EMBEDDING_PROVIDER"
    )
    embedding_model: str = Field(default="text-embedding-v4", alias="EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=1024, alias="EMBEDDING_DIMENSION")
    local_embedding_model: str = Field(default="BAAI/bge-m3", alias="LOCAL_EMBEDDING_MODEL")

    vector_backend: Literal["chroma", "faiss"] = Field(
        default="chroma", alias="VECTOR_BACKEND"
    )
    chroma_persist_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "indexes" / "chroma",
        alias="CHROMA_PERSIST_DIR",
    )
    chroma_collection_name: str = Field(
        default="medical_kb", alias="CHROMA_COLLECTION_NAME"
    )
    faiss_index_path: Path = Field(
        default=PROJECT_ROOT / "data" / "indexes" / "faiss" / "kb.index",
        alias="FAISS_INDEX_PATH",
    )

    chunk_size: int = Field(default=512, alias="CHUNK_SIZE")
    retrieval_top_k: int = Field(default=5, alias="RETRIEVAL_TOP_K")
    ingest_disease_limit: int = Field(default=400, alias="INGEST_DISEASE_LIMIT")

    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="", alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", alias="NEO4J_DATABASE")

    kg_schema_path: Path = Field(
        default=PROJECT_ROOT / "config" / "kg_schema.yaml", alias="KG_SCHEMA_PATH"
    )
    faq_dir: Path = Field(default=PROJECT_ROOT / "data" / "faq", alias="FAQ_DIR")

    redis_url: str = Field(default="", alias="REDIS_URL")
    mysql_dsn: str = Field(default="", alias="MYSQL_DSN")

    api_keys: str = Field(default="dev-key", alias="API_KEYS")
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    sqlite_path: Path = Field(
        default=PROJECT_ROOT / "data" / "sessions.db",
        alias="SQLITE_PATH",
    )
    history_max_turns: int = Field(default=12, alias="HISTORY_MAX_TURNS")
    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    frontend_dist: Path = Field(
        default=PROJECT_ROOT / "frontend" / "dist",
        alias="FRONTEND_DIST",
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="smart-medical-consultation", alias="LANGSMITH_PROJECT")
    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")


@lru_cache
def get_settings() -> Settings:
    return Settings()
