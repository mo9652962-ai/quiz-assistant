import pytest

from quiz_assistant.config import Settings


def test_enabled_ai_requires_an_allowlisted_https_endpoint(monkeypatch):
    monkeypatch.setenv("QUIZ_AI_ENABLED", "true")
    monkeypatch.setenv("QUIZ_AI_API_KEY", "test-key")
    monkeypatch.setenv("QUIZ_AI_MODEL", "test-model")
    monkeypatch.setenv("QUIZ_AI_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("QUIZ_AI_ALLOWED_BASE_URLS", "")

    settings = Settings.from_env()

    with pytest.raises(ValueError, match="allowlist"):
        settings.validate_ai()


def test_provider_text_redaction_removes_credentials_and_windows_paths():
    from quiz_assistant.infrastructure.ai.privacy import redact_provider_text

    value = "email alice@example.com key sk-test123 path C:\\Users\\alice\\quiz.db"

    redacted = redact_provider_text(value)

    assert "alice@example.com" not in redacted
    assert "sk-test123" not in redacted
    assert "C:\\Users\\alice" not in redacted

