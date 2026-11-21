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
    num_ctx: int = 4096

    chunk_size: int = 900
    chunk_overlap: int = 150
    top_k: int = 4
    score_threshold: float = 0.25
    history_limit: int = 4

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()