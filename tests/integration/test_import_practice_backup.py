import json
from pathlib import Path

from quiz_assistant.application.backup_service import create_backup, restore_backup
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
