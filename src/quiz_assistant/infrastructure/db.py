from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 2


class ManagedConnection(sqlite3.Connection):
    """Connection that closes after a ``with`` block (important on Windows)."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, factory=ManagedConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(path: str | Path) -> None:
    with connect(path) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS question_banks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
                subject TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL DEFAULT 1,
                source TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY, bank_id INTEGER NOT NULL REFERENCES question_banks(id),
                version INTEGER NOT NULL, type TEXT NOT NULL, stem TEXT NOT NULL,
                normalized_stem TEXT NOT NULL, answer_kind TEXT NOT NULL, explanation TEXT,
                status TEXT NOT NULL, difficulty REAL, source_json TEXT NOT NULL, tags_json TEXT NOT NULL,
                answer_aliases_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS options (
                id INTEGER PRIMARY KEY AUTOINCREMENT, question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                option_key TEXT NOT NULL, text TEXT NOT NULL, normalized_text TEXT NOT NULL, is_correct INTEGER NOT NULL,
                UNIQUE(question_id, option_key)
            );
            CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);
            CREATE TABLE IF NOT EXISTS question_tags (question_id TEXT REFERENCES questions(id) ON DELETE CASCADE, tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE, PRIMARY KEY(question_id, tag_id));
            CREATE TABLE IF NOT EXISTS practice_sessions (id TEXT PRIMARY KEY, mode TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT, filter_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS answer_events (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, question_id TEXT NOT NULL, question_version INTEGER NOT NULL, user_answer TEXT NOT NULL, is_correct INTEGER NOT NULL, match_method TEXT, confidence REAL, elapsed_ms INTEGER, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS review_state (question_id TEXT PRIMARY KEY REFERENCES questions(id) ON DELETE CASCADE, due_at TEXT, interval_days REAL NOT NULL, ease REAL NOT NULL, repetitions INTEGER NOT NULL, lapses INTEGER NOT NULL, scheduler TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ai_audits (id INTEGER PRIMARY KEY AUTOINCREMENT, question_text_hash TEXT NOT NULL, provider TEXT NOT NULL, model TEXT, request_json TEXT, response_json TEXT, parsed_json TEXT, validation_status TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_questions_bank_status ON questions(bank_id, status);
            CREATE INDEX IF NOT EXISTS idx_answer_events_question ON answer_events(question_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_review_due ON review_state(due_at);
            INSERT INTO schema_meta(key, value) VALUES ('version', '2') ON CONFLICT(key) DO UPDATE SET value=excluded.value;
            """
        )
        columns = {row["name"] for row in db.execute("PRAGMA table_info(questions)").fetchall()}
        if "answer_aliases_json" not in columns:
            db.execute(
                "ALTER TABLE questions ADD COLUMN answer_aliases_json TEXT NOT NULL DEFAULT '[]'"
            )
