import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv(
        'DATABASE_URL', 'postgresql+psycopg://partner:partner@127.0.0.1:5432/partner'))
    auth_url: str = field(default_factory=lambda: os.getenv('AUTH_URL', 'http://127.0.0.1:8002'))
    rag_url: str = field(default_factory=lambda: os.getenv('RAG_URL', 'http://127.0.0.1:8001'))
    allowed_origins: tuple[str, ...] = field(default_factory=lambda: tuple(
        value.strip().rstrip('/') for value in os.getenv('ALLOWED_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080'
        ).split(',') if value.strip()))
    # Number of complete question/answer pairs, not individual messages.
    history_turns: int = field(default_factory=lambda: int(os.getenv('HISTORY_TURNS', '10')))
    history_max_chars: int = field(default_factory=lambda: int(os.getenv('HISTORY_MAX_CHARS', '12000')))
    generation_timeout: float = field(default_factory=lambda: float(os.getenv('GENERATION_TIMEOUT', '110')))
    max_answer_chars: int = 100000
