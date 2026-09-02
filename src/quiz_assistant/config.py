from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("data/quiz.db")
    remote_enabled: bool = False
    remote_read_only: bool = False
    remote_host: str = "127.0.0.1"
    remote_port: int = 8765
    remote_public_origin: str | None = None
    remote_tls_proxy_enabled: bool = False
    remote_trusted_proxy_hosts: tuple[str, ...] = ()
    remote_database_url: str | None = None
    remote_allow_sqlite: bool = False
    remote_owner_username: str | None = None
    remote_owner_password: str | None = None
    ai_enabled: bool = False
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str | None = None
    ai_api_key: str | None = None
    ai_allowed_base_urls: tuple[str, ...] = ()
    ai_retention_days: int = 0
    ai_redact_sensitive: bool = True

    @classmethod
    def from_env(cls, db_path: str | Path | None = None) -> Settings:
        return cls(
            db_path=Path(db_path or os.getenv("QUIZ_DB_PATH", "data/quiz.db")),
            remote_enabled=_env_bool("QUIZ_REMOTE_ENABLED"),
            remote_read_only=_env_bool("QUIZ_REMOTE_READ_ONLY"),
            remote_host=os.getenv("QUIZ_REMOTE_HOST", "127.0.0.1").strip(),
            remote_port=int(os.getenv("QUIZ_REMOTE_PORT", "8765")),
            remote_public_origin=os.getenv("QUIZ_REMOTE_PUBLIC_ORIGIN") or None,
            remote_tls_proxy_enabled=_env_bool("QUIZ_REMOTE_TLS_PROXY_ENABLED"),
            remote_trusted_proxy_hosts=tuple(
                item.strip()
                for item in os.getenv("QUIZ_REMOTE_TRUSTED_PROXY_HOSTS", "").split(",")
                if item.strip()
            ),
            remote_database_url=os.getenv("QUIZ_DATABASE_URL") or None,
            remote_allow_sqlite=_env_bool("QUIZ_REMOTE_ALLOW_SQLITE"),
            remote_owner_username=os.getenv("QUIZ_REMOTE_OWNER_USERNAME") or None,
            remote_owner_password=os.getenv("QUIZ_REMOTE_OWNER_PASSWORD") or None,
            ai_enabled=_env_bool("QUIZ_AI_ENABLED"),
            ai_base_url=os.getenv("QUIZ_AI_BASE_URL", "https://api.openai.com/v1"),
            ai_model=os.getenv("QUIZ_AI_MODEL") or None,
            ai_api_key=os.getenv("QUIZ_AI_API_KEY") or None,
            ai_allowed_base_urls=tuple(
                item.strip().rstrip("/")
                for item in os.getenv("QUIZ_AI_ALLOWED_BASE_URLS", "").split(",")
                if item.strip()
            ),
            ai_retention_days=int(os.getenv("QUIZ_AI_RETENTION_DAYS", "0")),
            ai_redact_sensitive=_env_bool("QUIZ_AI_REDACT_SENSITIVE", "true"),
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

    def validate_remote(self) -> None:
        """Validate the Phase C remote read-only deployment boundary."""
        if not self.remote_enabled:
            return
        if not self.remote_read_only:
            raise ValueError("remote Phase C requires read-only mode")
        if self.remote_host != "127.0.0.1":
            raise ValueError("remote application must bind to loopback")
        if not 1 <= self.remote_port <= 65535:
            raise ValueError("remote port must be between 1 and 65535")
        if not self.remote_tls_proxy_enabled:
            raise ValueError("remote mode requires a trusted TLS proxy")
        if not self.remote_public_origin:
            raise ValueError("remote mode requires a public HTTPS origin")
        origin = urlsplit(self.remote_public_origin)
        if origin.scheme != "https" or not origin.netloc or origin.path not in {"", "/"}:
            raise ValueError("remote public origin must be an HTTPS origin")
        if not self.remote_trusted_proxy_hosts:
            raise ValueError("remote mode requires a trusted proxy host list")
        if not self.remote_owner_username or not self.remote_owner_password:
            raise ValueError("remote mode requires an explicit initial owner")
        if self.remote_owner_username == "local-owner":
            raise ValueError("remote owner must not use the local-owner account")
        if not self.remote_database_url:
            if not self.remote_allow_sqlite:
                raise ValueError("remote mode requires PostgreSQL or an explicit SQLite transition")
        else:
            database_scheme = urlsplit(self.remote_database_url).scheme
            if database_scheme in {"postgres", "postgresql"}:
                return
            if database_scheme == "sqlite" and self.remote_allow_sqlite:
                return
            raise ValueError("remote database must be PostgreSQL unless SQLite transition is explicit")

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        for name in ("raw", "exports", "backups"):
            (self.db_path.parent / name).mkdir(parents=True, exist_ok=True)
