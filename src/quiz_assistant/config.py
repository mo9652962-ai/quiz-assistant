from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("data/quiz.db")
    ai_enabled: bool = False
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str | None = None
    ai_api_key: str | None = None
    ai_allowed_base_urls: tuple[str, ...] = ()
    ai_retention_days: int = 0
    ai_redact_sensitive: bool = True

    @classmethod
    def from_env(cls, db_path: str | Path | None = None) -> Settings:
        raw_enabled = os.getenv("QUIZ_AI_ENABLED", "false").strip().lower()
        return cls(
            db_path=Path(db_path or os.getenv("QUIZ_DB_PATH", "data/quiz.db")),
            ai_enabled=raw_enabled in {"1", "true", "yes", "on"},
            ai_base_url=os.getenv("QUIZ_AI_BASE_URL", "https://api.openai.com/v1"),
            ai_model=os.getenv("QUIZ_AI_MODEL") or None,
            ai_api_key=os.getenv("QUIZ_AI_API_KEY") or None,
            ai_allowed_base_urls=tuple(
                item.strip().rstrip("/")
                for item in os.getenv("QUIZ_AI_ALLOWED_BASE_URLS", "").split(",")
                if item.strip()
            ),
            ai_retention_days=int(os.getenv("QUIZ_AI_RETENTION_DAYS", "0")),
            ai_redact_sensitive=os.getenv("QUIZ_AI_REDACT_SENSITIVE", "true")
            .strip()
            .lower()
            in {"1", "true", "yes", "on"},
        )

    def validate_ai(self) -> None:
        if not self.ai_enabled:
            return
        if not self.ai_api_key or not self.ai_model:
            raise ValueError("enabled AI requires an API key and model")
        parsed = urlsplit(self.ai_base_url)
        normalized = self.ai_base_url.rstrip("/")
        if parsed.scheme != "https":
            raise ValueError("AI provider must use HTTPS")
        if normalized not in self.ai_allowed_base_urls:
            raise ValueError("AI provider base URL is not in the allowlist")
        if self.ai_retention_days < 0:
            raise ValueError("AI retention days must not be negative")

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        for name in ("raw", "exports", "backups"):
            (self.db_path.parent / name).mkdir(parents=True, exist_ok=True)
