# Tests use explicit settings, independently of a developer's local .env file.
from app import config
config.settings = config.Settings(
    _env_file=None,
    qdrant_url="http://127.0.0.1:1",
    ollama_url="http://127.0.0.1:1",
    fastembed_cache_path="/tmp/partner-test-fastembed",
    rerank_enabled=True,
    rewrite_enabled=True,
    rerank_low_threshold=0.20,
    rerank_high_threshold=0.45,
    score_threshold=0.25,
)
