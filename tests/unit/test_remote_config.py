import pytest

from quiz_assistant.config import Settings


def test_remote_read_only_requires_loopback_tls_and_database_boundary(monkeypatch):
    monkeypatch.setenv("QUIZ_REMOTE_ENABLED", "true")
    monkeypatch.setenv("QUIZ_REMOTE_READ_ONLY", "true")
    monkeypatch.setenv("QUIZ_REMOTE_HOST", "127.0.0.1")
    monkeypatch.setenv("QUIZ_REMOTE_PUBLIC_ORIGIN", "https://quiz.example.test")
    monkeypatch.setenv("QUIZ_REMOTE_TLS_PROXY_ENABLED", "true")
    monkeypatch.setenv("QUIZ_REMOTE_TRUSTED_PROXY_HOSTS", "127.0.0.1")
    monkeypatch.setenv("QUIZ_DATABASE_URL", "postgresql://quiz@localhost/quiz")
    monkeypatch.setenv("QUIZ_REMOTE_OWNER_USERNAME", "remote-owner")
    monkeypatch.setenv("QUIZ_REMOTE_OWNER_PASSWORD", "change-me-now")

    settings = Settings.from_env()

    settings.validate_remote()
    assert settings.remote_enabled is True
    assert settings.remote_read_only is True
    assert settings.remote_database_url == "postgresql://quiz@localhost/quiz"


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("QUIZ_REMOTE_READ_ONLY", "false", "read-only"),
        ("QUIZ_REMOTE_HOST", "0.0.0.0", "loopback"),
        ("QUIZ_REMOTE_TLS_PROXY_ENABLED", "false", "TLS"),
        ("QUIZ_REMOTE_PUBLIC_ORIGIN", "http://quiz.example.test", "HTTPS"),
        ("QUIZ_REMOTE_TRUSTED_PROXY_HOSTS", "", "trusted proxy"),
    ],
)
def test_remote_mode_rejects_unsafe_runtime_configuration(monkeypatch, name, value, message):
    monkeypatch.setenv("QUIZ_REMOTE_ENABLED", "true")
    monkeypatch.setenv("QUIZ_REMOTE_READ_ONLY", "true")
    monkeypatch.setenv("QUIZ_REMOTE_HOST", "127.0.0.1")
    monkeypatch.setenv("QUIZ_REMOTE_PUBLIC_ORIGIN", "https://quiz.example.test")
    monkeypatch.setenv("QUIZ_REMOTE_TLS_PROXY_ENABLED", "true")
    monkeypatch.setenv("QUIZ_REMOTE_TRUSTED_PROXY_HOSTS", "127.0.0.1")
    monkeypatch.setenv("QUIZ_DATABASE_URL", "postgresql://quiz@localhost/quiz")
    monkeypatch.setenv("QUIZ_REMOTE_OWNER_USERNAME", "remote-owner")
    monkeypatch.setenv("QUIZ_REMOTE_OWNER_PASSWORD", "change-me-now")
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=message):
        Settings.from_env().validate_remote()


def test_remote_mode_requires_postgres_unless_sqlite_transition_is_explicit(monkeypatch):
    monkeypatch.setenv("QUIZ_REMOTE_ENABLED", "true")
    monkeypatch.setenv("QUIZ_REMOTE_READ_ONLY", "true")
    monkeypatch.setenv("QUIZ_REMOTE_HOST", "127.0.0.1")
    monkeypatch.setenv("QUIZ_REMOTE_PUBLIC_ORIGIN", "https://quiz.example.test")
    monkeypatch.setenv("QUIZ_REMOTE_TLS_PROXY_ENABLED", "true")
    monkeypatch.setenv("QUIZ_REMOTE_TRUSTED_PROXY_HOSTS", "127.0.0.1")
    monkeypatch.setenv("QUIZ_REMOTE_OWNER_USERNAME", "remote-owner")
    monkeypatch.setenv("QUIZ_REMOTE_OWNER_PASSWORD", "change-me-now")

    with pytest.raises(ValueError, match="PostgreSQL|SQLite transition"):
        Settings.from_env().validate_remote()

    monkeypatch.setenv("QUIZ_REMOTE_ALLOW_SQLITE", "true")
    settings = Settings.from_env()
    settings.validate_remote()
    assert settings.remote_allow_sqlite is True
