"""ASGI entry point for the guarded remote pilot.

The module intentionally does not open a database connection at import time. The
application lifespan performs initialization after the server has started.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from quiz_assistant.api.app import create_app
from quiz_assistant.config import Settings


def create_configured_app():
    settings = Settings.from_env()
    settings.validate_ai()
    settings.validate_remote()
    database_url = settings.remote_database_url if settings.remote_enabled else None
    return create_app(
        db_path=settings.db_path,
        database_url=database_url,
        session_token=settings.local_session_token,
        ai_enabled=settings.ai_enabled,
        auth_mode="accounts" if settings.remote_enabled else "local",
        secure_cookies=settings.remote_enabled,
        remote_read_only=settings.remote_enabled and settings.remote_read_only,
        remote_owner_username=settings.remote_owner_username,
        remote_owner_password=settings.remote_owner_password,
        allowed_hosts=[urlsplit(settings.remote_public_origin).hostname]
        if settings.remote_enabled and settings.remote_public_origin
        else None,
    )


app = create_configured_app()
