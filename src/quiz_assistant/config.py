from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("data/quiz.db")
    ai_enabled: bool = False
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str | None = None
    ai_api_key: str | None = None

    @classmethod
    def from_env(cls, db_path: str | Path | None = None) -> Settings:
        raw_enabled = os.getenv("QUIZ_AI_ENABLED", "false").strip().lower()
        return cls(
            db_path=Path(db_path or os.getenv("QUIZ_DB_PATH", "data/quiz.db")),
            ai_enabled=raw_enabled in {"1", "true", "yes", "on"},
            ai_base_url=os.getenv("QUIZ_AI_BASE_URL", "https://api.openai.com/v1"),
            ai_model=os.getenv("QUIZ_AI_MODEL") or None,
            ai_api_key=os.getenv("QUIZ_AI_API_KEY") or None,
        )

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        for name in ("raw", "exports", "backups"):
            (self.db_path.parent / name).mkdir(parents=True, exist_ok=True)
