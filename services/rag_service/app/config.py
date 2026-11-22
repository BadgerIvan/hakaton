from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ollama_url: str = "http://ollama:11434"
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "company_docs"
    data_dir: str = "/app/data"

    llm_model: str = "qwen3:4b"
    llm_reasoning: bool = False
    embed_model: str = "bge-m3"
    embed_dim: int = 1024
    sparse_model: str = "Qdrant/bm25"
    bm25_language: str = "russian"
    num_ctx: int = 8192

    chunk_size: int = 900
    chunk_overlap: int = 150
    retrieval_k: int = 12
    top_k: int = 4
    score_threshold: float = 0.25
    history_limit: int = 6

    rerank_enabled: bool = True
    rerank_threads: int = 2
    rerank_model: str = "jinaai/jina-reranker-v2-base-multilingual"
    rerank_high_threshold: float = 0.45
    rerank_low_threshold: float = 0.20
    fastembed_cache_path: str = "/app/.fastembed_cache"

    rewrite_enabled: bool = True
    rewrite_history_limit: int = 4

    admin_token: str = "12181218"
    max_upload_mb: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
