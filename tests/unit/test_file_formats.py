from pathlib import Path

from quiz_assistant.application.import_service import import_questions
from quiz_assistant.infrastructure.db import connect


def test_jsonl_import_reads_one_question_per_line(tmp_path: Path):
    source = tmp_path / "questions.jsonl"
    source.write_text(
        '{"id":"jsonl-1","bank":"jsonl","type":"single_choice","stem":"One plus one?","options":[{"key":"A","text":"1"},{"key":"B","text":"2","correct":true}]}\n'
        '{"id":"jsonl-2","bank":"jsonl","type":"short_answer","stem":"Capital of France?","answer_aliases":["Paris"]}\n',
        encoding="utf-8",
    )
    db_path = tmp_path / "quiz.db"

    report = import_questions(source, db_path)

    assert report.total == 2
    assert report.imported == 2
    with connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 2


def test_dry_run_jsonl_does_not_write_questions(tmp_path: Path):
    source = tmp_path / "questions.jsonl"
    source.write_text(
        '{"id":"jsonl-dry","bank":"jsonl","type":"single_choice","stem":"Dry run?","options":[{"key":"A","text":"yes","correct":true},{"key":"B","text":"no"}]}\n',
        encoding="utf-8",
    )
    db_path = tmp_path / "quiz.db"

    report = import_questions(source, db_path, dry_run=True)

    assert report.imported == 1
    with connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 0


def test_invalid_jsonl_row_is_rejected_without_stopping_following_rows(tmp_path: Path):
    source = tmp_path / "questions.jsonl"
    source.write_text(
        '{"id":"jsonl-good","bank":"jsonl","type":"single_choice","stem":"Good?","options":[{"key":"A","text":"yes","correct":true},{"key":"B","text":"no"}]}\n'
        '{not valid json}\n'
        '{"id":"jsonl-good-2","bank":"jsonl","type":"single_choice","stem":"Good two?","options":[{"key":"A","text":"yes","correct":true},{"key":"B","text":"no"}]}\n',
        encoding="utf-8",
    )
    db_path = tmp_path / "quiz.db"

    report = import_questions(source, db_path)

    assert report.total == 3
    assert report.imported == 2
    assert report.rejected_count == 1
    with connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 2
