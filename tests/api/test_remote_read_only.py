from pathlib import Path

from fastapi.testclient import TestClient

from quiz_assistant.api.app import create_app
from quiz_assistant.application.import_service import import_questions


def test_remote_read_only_allows_queries_but_blocks_data_writes(tmp_path: Path):
    db_path = tmp_path / "quiz.db"
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_questions.json"
    import_questions(fixture, db_path)
    client = TestClient(
        create_app(db_path=db_path, session_token="test-session", remote_read_only=True)
    )
    headers = {"X-Quiz-Session": "test-session"}

    banks = client.get("/api/banks", headers=headers)
    assert banks.status_code == 200

    query = client.post(
        "/api/queries",
        headers=headers,
        json={"text": "Which sentence is grammatically correct?"},
    )
    assert query.status_code == 200

    practice = client.post(
        "/api/practice/sessions",
        headers=headers,
        json={"bank": "english-basic", "count": 1},
    )
    assert practice.status_code == 403
    assert practice.json()["code"] == "remote_read_only"


def test_remote_read_only_blocks_import_and_backup_even_for_local_owner(tmp_path: Path):
    db_path = tmp_path / "quiz.db"
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_questions.json"
    import_questions(fixture, db_path)
    client = TestClient(
        create_app(db_path=db_path, session_token="test-session", remote_read_only=True)
    )
    headers = {"X-Quiz-Session": "test-session"}

    imported = client.post(
        "/api/imports",
        headers=headers,
        files={"file": ("sample_questions.json", fixture.read_bytes(), "application/json")},
    )
    assert imported.status_code == 403
    assert imported.json()["code"] == "remote_read_only"

    backup = client.post("/api/backups", headers=headers, json={"action": "create"})
    assert backup.status_code == 403
    assert backup.json()["code"] == "remote_read_only"
