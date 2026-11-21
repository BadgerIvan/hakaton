import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "postgresql+psycopg://partner:partner@127.0.0.1:5432/partner")
    )
    allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip().rstrip("/")
            for origin in os.getenv(
                "ALLOWED_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080",
            ).split(",")
            if origin.strip()
        )
    )
    cookie_name: str = "partner_session"
    cookie_secure: bool = field(
        default_factory=lambda: os.getenv("COOKIE_SECURE", "false").lower() == "true"
    )
    session_days: int = 7
    rate_window_seconds: int = 900
    login_ip_limit: int = 40
    login_email_limit: int = 10
    register_ip_limit: int = 10
