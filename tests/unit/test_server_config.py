from quiz_assistant.server import create_configured_app


def _set_valid_remote_env(monkeypatch):
    monkeypatch.setenv("QUIZ_REMOTE_ENABLED", "true")
    monkeypatch.setenv("QUIZ_REMOTE_READ_ONLY", "true")
    monkeypatch.setenv("QUIZ_REMOTE_HOST", "127.0.0.1")
    monkeypatch.setenv("QUIZ_REMOTE_PUBLIC_ORIGIN", "https://quiz.example.test")
    monkeypatch.setenv("QUIZ_REMOTE_TLS_PROXY_ENABLED", "true")
    monkeypatch.setenv("QUIZ_REMOTE_TRUSTED_PROXY_HOSTS", "127.0.0.1")
    monkeypatch.setenv("QUIZ_REMOTE_ALLOW_SQLITE", "true")
    monkeypatch.setenv("QUIZ_REMOTE_OWNER_USERNAME", "remote-owner")
    monkeypatch.setenv("QUIZ_REMOTE_OWNER_PASSWORD", "change-me-now")
    monkeypatch.delenv("QUIZ_DATABASE_URL", raising=False)


def test_configured_server_enables_accounts_and_read_only_pilot(monkeypatch, tmp_path):
    _set_valid_remote_env(monkeypatch)
    monkeypatch.setenv("QUIZ_DB_PATH", str(tmp_path / "quiz.db"))

    app = create_configured_app()

    assert app.state.auth_mode == "accounts"
    assert app.state.secure_cookies is True
    assert app.state.remote_read_only is True
    assert any(m.cls.__name__ == "TrustedHostMiddleware" for m in app.user_middleware)


def test_configured_server_accepts_postgres_target_for_database_abstraction(monkeypatch):
    _set_valid_remote_env(monkeypatch)
    monkeypatch.setenv("QUIZ_REMOTE_ALLOW_SQLITE", "false")
    monkeypatch.setenv("QUIZ_DATABASE_URL", "postgresql://quiz@localhost/quiz")

    app = create_configured_app()

    assert app.state.db_target == "postgresql://quiz@localhost/quiz"
