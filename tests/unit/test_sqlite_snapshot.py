import json
from pathlib import Path

from quiz_assistant.application.import_service import import_questions
from quiz_assistant.infrastructure.db import connect
from quiz_assistant.infrastructure.sqlite_snapshot import (
    export_sqlite_snapshot,
    import_sqlite_snapshot,
)


def test_sqlite_snapshot_round_trip_excludes_sessions(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_questions.json"
    import_questions(fixture, source_db)

    snapshot = tmp_path / "migration.snapshot.json"
    exported = export_sqlite_snapshot(source_db, snapshot)
    payload = json.loads(snapshot.read_text(encoding="utf-8"))

    assert exported.question_count == 3
    assert payload["format"] == "quiz-assistant-sqlite-snapshot"
    assert "sessions" not in payload["tables"]
    assert "password_hash" in payload["tables"]["users"][0]

    imported = import_sqlite_snapshot(snapshot, target_db)

    assert imported.question_count == 3
    with connect(target_db) as db:
        assert db.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_sqlite_snapshot_import_rejects_invalid_format_without_creating_database(tmp_path: Path):
    snapshot = tmp_path / "invalid.json"
    target_db = tmp_path / "target.db"
    snapshot.write_text(json.dumps({"format": "other"}), encoding="utf-8")

    try:
        import_sqlite_snapshot(snapshot, target_db)
    except ValueError as exc:
        assert "snapshot format" in str(exc)
    else:
        raise AssertionError("invalid snapshot should be rejected")

    assert not target_db.exists()
