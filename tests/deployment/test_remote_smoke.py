from pathlib import Path

from fastapi.testclient import TestClient

from quiz_assistant.api.app import create_app
from quiz_assistant.application.import_service import import_questions


def test_remote_deployment_smoke_covers_login_reads_and_read_only_gate(tmp_path: Path):
    db_path = tmp_path / "quiz.db"
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_questions.json"
    import_questions(fixture, db_path)
    app = create_app(
        db_path=db_path,
        auth_mode="accounts",
        secure_cookies=True,
        remote_read_only=True,
        remote_owner_username="staging-owner",
        remote_owner_password="staging-password",
        allowed_hosts=["quiz.example.test"],
    )

    with TestClient(app, base_url="https://quiz.example.test") as client:
        health = client.get("/api/health")
        assert health.status_code == 200

        login = client.post(
            "/api/auth/login",
            json={"username": "staging-owner", "password": "staging-password"},
        )
        assert login.status_code == 200

        banks = client.get("/api/banks")
        assert banks.status_code == 200
        query = client.post(
            "/api/queries",
            json={"text": "Which sentence is grammatically correct?"},
        )
        assert query.status_code == 200

        write_attempt = client.post(
            "/api/practice/sessions",
            json={"bank": "english-basic", "count": 1},
        )
        assert write_attempt.status_code == 403
        assert write_attempt.json()["code"] == "remote_read_only"


def test_caddy_example_keeps_fastapi_on_loopback():
    caddy = Path(__file__).parents[2] / "deploy" / "Caddyfile.example"
    content = caddy.read_text(encoding="utf-8")

    assert "reverse_proxy 127.0.0.1:8765" in content
    assert "Strict-Transport-Security" in content
    assert "0.0.0.0:8765" not in content
