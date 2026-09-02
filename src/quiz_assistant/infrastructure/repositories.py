from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime

from quiz_assistant.domain.matcher import normalize_text
from quiz_assistant.domain.models import ReviewItem
from quiz_assistant.schemas.question import (
    Option,
    Question,
    QuestionStatus,
    QuestionType,
    SourceRef,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def ensure_bank(
    db: sqlite3.Connection,
    name: str,
    source: str | None = None,
    workspace_id: str = "local-default",
) -> int:
    db.execute(
        "INSERT OR IGNORE INTO question_banks(name, source, workspace_id, created_at) VALUES (?, ?, ?, ?)",
        (name, source, workspace_id, utc_now()),
    )
    row = db.execute(
        "SELECT id FROM question_banks WHERE name = ? AND workspace_id = ?",
        (name, workspace_id),
    ).fetchone()
    if not row:
        raise ValueError(f"question bank {name!r} already belongs to another workspace")
    return int(row[0])


def question_exists(
    db: sqlite3.Connection, question_id: str, workspace_id: str | None = None
) -> bool:
    query = "SELECT 1 FROM questions q JOIN question_banks b ON b.id = q.bank_id WHERE q.id = ?"
    params: list[object] = [question_id]
    if workspace_id:
        query += " AND b.workspace_id = ?"
        params.append(workspace_id)
    return db.execute(query, params).fetchone() is not None


def insert_question(
    db: sqlite3.Connection,
    question: Question,
    source_file: str | None = None,
    workspace_id: str = "local-default",
) -> None:
    bank_id = ensure_bank(db, question.bank, source_file, workspace_id)
    db.execute(
        """INSERT INTO questions(id, bank_id, version, type, stem, normalized_stem, answer_kind, explanation, status, difficulty, source_json, tags_json, answer_aliases_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            question.id,
            bank_id,
            question.version,
            question.type.value,
            question.stem,
            normalize_text(question.stem),
            "choice" if question.options else "short_answer",
            question.explanation,
            question.status.value,
            None,
            question.source.model_dump_json(),
            json.dumps(question.tags, ensure_ascii=False),
            json.dumps(question.answer_aliases, ensure_ascii=False),
        ),
    )
    for option in question.options:
        db.execute(
            "INSERT INTO options(question_id, option_key, text, normalized_text, is_correct) VALUES (?, ?, ?, ?, ?)",
            (
                question.id,
                option.key,
                option.text,
                normalize_text(option.text, strip_option_prefix=True),
                int(option.correct),
            ),
        )
    for tag in question.tags:
        db.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (tag,))
        tag_id = db.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()[0]
        db.execute(
            "INSERT OR IGNORE INTO question_tags(question_id, tag_id) VALUES (?, ?)",
            (question.id, tag_id),
        )


def row_to_question(db: sqlite3.Connection, row: sqlite3.Row) -> Question:
    options = db.execute(
        "SELECT option_key, text, is_correct FROM options WHERE question_id = ? ORDER BY id",
        (row["id"],),
    ).fetchall()
    source = json.loads(row["source_json"])
    return Question(
        id=row["id"],
        bank=db.execute(
            "SELECT name FROM question_banks WHERE id = ?", (row["bank_id"],)
        ).fetchone()[0],
        version=row["version"],
        type=QuestionType(row["type"]),
        stem=row["stem"],
        options=[
            Option(key=item["option_key"], text=item["text"], correct=bool(item["is_correct"]))
            for item in options
        ],
        explanation=row["explanation"],
        tags=json.loads(row["tags_json"]),
        source=SourceRef.model_validate(source),
        status=QuestionStatus(row["status"]),
        answer_aliases=json.loads(row["answer_aliases_json"]),
    )


def list_questions(
    db: sqlite3.Connection,
    bank: str | None = None,
    status: str = "active",
    tag: str | None = None,
    workspace_id: str | None = None,
) -> list[Question]:
    query = (
        "SELECT q.* FROM questions q JOIN question_banks b ON b.id = q.bank_id WHERE q.status = ?"
    )
    params: list[object] = [status]
    if workspace_id:
        query += " AND b.workspace_id = ?"
        params.append(workspace_id)
    if bank:
        query += " AND b.name = ?"
        params.append(bank)
    if tag:
        query += " AND EXISTS (SELECT 1 FROM question_tags qt JOIN tags t ON t.id=qt.tag_id WHERE qt.question_id=q.id AND t.name=?)"
        params.append(tag)
    query += " ORDER BY q.id"
    return [row_to_question(db, row) for row in db.execute(query, params).fetchall()]


def get_question(
    db: sqlite3.Connection, question_id: str, workspace_id: str | None = None
) -> Question | None:
    query = "SELECT q.* FROM questions q JOIN question_banks b ON b.id = q.bank_id WHERE q.id = ?"
    params: list[object] = [question_id]
    if workspace_id:
        query += " AND b.workspace_id = ?"
        params.append(workspace_id)
    row = db.execute(query, params).fetchone()
    return row_to_question(db, row) if row else None


def create_session(
    db: sqlite3.Connection,
    mode: str,
    filter_json: str = "{}",
    user_id: str = "local-owner",
    workspace_id: str = "local-default",
) -> str:
    session_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO practice_sessions(id, mode, started_at, filter_json, user_id, workspace_id) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, mode, utc_now(), filter_json, user_id, workspace_id),
    )
    return session_id


def record_answer(
    db: sqlite3.Connection,
    session_id: str,
    question: Question,
    user_answer: str,
    method: str | None,
    confidence: float | None,
    elapsed_ms: int | None,
    user_id: str = "local-owner",
    workspace_id: str = "local-default",
) -> bool:
    submitted = {
        part.strip().upper() for part in user_answer.replace(";", ",").split(",") if part.strip()
    }
    expected = {option.key for option in question.options if option.correct}
    if not expected and question.answer_aliases:
        normalized = normalize_text(user_answer)
        is_correct = normalized in {normalize_text(alias) for alias in question.answer_aliases}
    else:
        is_correct = submitted == expected
    db.execute(
        "INSERT INTO answer_events(session_id, question_id, question_version, user_answer, is_correct, match_method, confidence, elapsed_ms, created_at, user_id, workspace_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            session_id,
            question.id,
            question.version,
            user_answer,
            int(is_correct),
            method,
            confidence,
            elapsed_ms,
            utc_now(),
            user_id,
            workspace_id,
        ),
    )
    return is_correct


def get_review_items(
    db: sqlite3.Connection,
    *,
    wrong: bool = False,
    due: bool = False,
    limit: int = 20,
    user_id: str = "local-owner",
    workspace_id: str = "local-default",
) -> list[ReviewItem]:
    query = """SELECT q.*, rs.due_at, rs.interval_days, rs.ease, rs.repetitions, rs.lapses
               FROM questions q JOIN review_state rs ON rs.question_id=q.id
               JOIN question_banks b ON b.id=q.bank_id
               WHERE rs.user_id = ? AND rs.workspace_id = ? AND b.workspace_id = ?"""
    params: list[object] = [user_id, workspace_id, workspace_id]
    if wrong:
        query += " AND EXISTS (SELECT 1 FROM answer_events ae WHERE ae.question_id=q.id AND ae.user_id=? AND ae.workspace_id=? AND ae.is_correct=0)"
        params.extend([user_id, workspace_id])
    if due:
        query += " AND (rs.due_at IS NULL OR rs.due_at <= ?)"
        params.append(utc_now())
    query += " ORDER BY COALESCE(rs.due_at, '') LIMIT ?"
    params.append(limit)
    result = []
    for row in db.execute(query, params).fetchall():
        result.append(
            ReviewItem(
                row_to_question(db, row),
                datetime.fromisoformat(row["due_at"]) if row["due_at"] else None,
                row["interval_days"],
                row["ease"],
                row["repetitions"],
                row["lapses"],
            )
        )
    return result
