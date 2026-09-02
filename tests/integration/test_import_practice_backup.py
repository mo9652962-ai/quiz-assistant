import inspect
import json
from pathlib import Path

import pytest

from quiz_assistant.application.backup_service import (
    _online_backup,
    create_backup,
    restore_backup,
    sha256,
)
from quiz_assistant.application.import_service import import_questions
from quiz_assistant.application.practice_service import submit_answer
from quiz_assistant.application.query_service import query_questions
from quiz_assistant.infrastructure.db import connect


def test_import_query_practice_and_restore(tmp_path: Path):
    source = tmp_path / "questions.json"
    source.write_text(
        json.dumps(
            [
                {
                    "id": "q-1",
                    "bank": "demo",
                    "type": "single_choice",
                    "stem": "2 + 2?",
                    "options": [
                        {"key": "A", "text": "3"},
                        {"key": "B", "text": "4", "correct": True},
                    ],
                },
                {
                    "id": "broken",
                    "bank": "demo",
                    "type": "single_choice",
                    "stem": "bad",
                    "options": [{"key": "A", "text": "x"}, {"key": "B", "text": "y"}],
                },
            ]
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "data" / "quiz.db"
    report = import_questions(source, db_path)
    assert (report.imported, report.rejected_count) == (1, 1)
    assert query_questions(db_path, " ２ ＋ ２？ ").answer_keys == ["B"]
    correct, session = submit_answer(db_path, "q-1", "B")
    assert correct and session
    with connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM answer_events").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM review_state").fetchone()[0] == 1
    backup = create_backup(db_path, tmp_path / "backups")
    db_path.unlink()
    restore_backup(backup, db_path)
    assert db_path.exists()


def test_duplicate_import_does_not_duplicate_question(tmp_path: Path):
    source = tmp_path / "questions.json"
    source.write_text(
        json.dumps(
            {
                "id": "q-1",
                "bank": "demo",
                "type": "short_answer",
                "stem": "capital",
                "answer_aliases": ["Paris"],
            }
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "quiz.db"
    assert import_questions(source, db_path).imported == 1
    assert import_questions(source, db_path).skipped_duplicate == 1


def test_online_backup_is_sqlite_consistent_and_manifested(tmp_path: Path):
    db_path = tmp_path / "quiz.db"
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_questions.json"
    import_questions(fixture, db_path)

    backup = create_backup(db_path, tmp_path / "backups")
    backup_db = backup / db_path.name

    assert ".backup(" in inspect.getsource(_online_backup)
    with connect(backup_db) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 3


def test_restore_rejects_database_that_passes_hash_but_fails_integrity(tmp_path: Path):
    db_path = tmp_path / "quiz.db"
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_questions.json"
    import_questions(fixture, db_path)
    backup = create_backup(db_path, tmp_path / "backups")
    backup_db = backup / db_path.name
    backup_db.write_bytes(b"not a sqlite database")
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"][db_path.name] = sha256(backup_db)
    (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="integrity"):
        restore_backup(backup, db_path, force=True)
    with connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 3


def test_short_answer_aliases_survive_database_roundtrip(tmp_path: Path):
    source = tmp_path / "questions.json"
    source.write_text(
        json.dumps(
            {
                "id": "q-short",
                "bank": "demo",
                "type": "short_answer",
                "stem": "capital",
                "answer_aliases": ["Paris", "巴黎"],
            }
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "quiz.db"
    import_questions(source, db_path)
    correct, _ = submit_answer(db_path, "q-short", "巴黎")
    assert correct


def test_csv_bom_and_dry_run(tmp_path: Path):
    source = Path(__file__).parents[1] / "fixtures" / "sample.csv"
    db_path = tmp_path / "quiz.db"
    report = import_questions(source, db_path, dry_run=True)
    assert (report.total, report.imported, report.rejected_count) == (2, 2, 0)
    with connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 0
    assert import_questions(source, db_path).imported == 2
