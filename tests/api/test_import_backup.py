from pathlib import Path

from fastapi.testclient import TestClient

from quiz_assistant.api.app import create_app
from quiz_assistant.application.import_service import import_questions


def test_import_dry_run_and_explicit_backup_overwrite(tmp_path: Path):
    db_path = tmp_path / "quiz.db"
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_questions.json"
    import_questions(fixture, db_path)
    client = TestClient(create_app(db_path=db_path, session_token="test-session"))
    headers = {"X-Quiz-Session": "test-session"}

    imported = client.post(
        "/api/imports",
        headers=headers,
        files={"file": ("sample_questions.json", fixture.read_bytes(), "application/json")},
        data={"dry_run": "true"},
    )
    assert imported.status_code == 200
    assert imported.json()["dry_run"] is True

    created = client.post("/api/backups", headers=headers, json={"action": "create"})
    assert created.status_code == 200
    backup_id = created.json()["backup_id"]

    restore = {"action": "restore", "backup_id": backup_id, "confirm": "RESTORE_CURRENT_DATABASE"}
    assert client.post("/api/backups", headers=headers, json=restore).status_code == 409
    restore["force"] = True
    restored = client.post("/api/backups", headers=headers, json=restore)
    assert restored.status_code == 200
    assert restored.json()["verified"] is True

