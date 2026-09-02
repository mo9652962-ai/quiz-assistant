from __future__ import annotations

import sqlite3
from pathlib import Path

from quiz_assistant.infrastructure.passwords import hash_password

SCHEMA_VERSION = 3


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
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, email TEXT UNIQUE,
                password_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
                global_role TEXT NOT NULL DEFAULT 'user', created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workspace_memberships (
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(workspace_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                workspace_id TEXT REFERENCES workspaces(id) ON DELETE SET NULL,
                token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL, revoked_at TEXT
            );
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
            """
        )
        _add_column(db, "questions", "answer_aliases_json TEXT NOT NULL DEFAULT '[]'")
        _add_column(db, "question_banks", "workspace_id TEXT")
        _add_column(db, "practice_sessions", "user_id TEXT")
        _add_column(db, "practice_sessions", "workspace_id TEXT")
        _add_column(db, "answer_events", "user_id TEXT")
        _add_column(db, "answer_events", "workspace_id TEXT")

        _ensure_review_state_v3(db)

        now = "2026-09-02T00:00:00+00:00"
        db.execute(
            "INSERT OR IGNORE INTO workspaces(id, name, created_at) VALUES ('local-default', 'Local default', ?)",
            (now,),
        )
        db.execute(
            "INSERT OR IGNORE INTO users(id, username, password_hash, status, global_role, created_at) VALUES ('local-owner', 'local-owner', ?, 'active', 'owner', ?)",
            (hash_password("local-owner"), now),
        )
        db.execute(
            """INSERT OR IGNORE INTO workspace_memberships(workspace_id, user_id, role, created_at)
               VALUES ('local-default', 'local-owner', 'owner', ?)""",
            (now,),
        )
        db.execute(
            "UPDATE question_banks SET workspace_id = 'local-default' WHERE workspace_id IS NULL"
        )
        db.execute(
            "UPDATE practice_sessions SET user_id = 'local-owner', workspace_id = 'local-default' WHERE user_id IS NULL OR workspace_id IS NULL"
        )
        db.execute(
            "UPDATE answer_events SET user_id = 'local-owner', workspace_id = 'local-default' WHERE user_id IS NULL OR workspace_id IS NULL"
        )
        db.execute(
            "UPDATE review_state SET user_id = 'local-owner', workspace_id = 'local-default' WHERE user_id IS NULL OR workspace_id IS NULL"
        )
        db.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_question_banks_workspace ON question_banks(workspace_id, name);
            CREATE INDEX IF NOT EXISTS idx_practice_sessions_user ON practice_sessions(user_id, started_at);
            CREATE INDEX IF NOT EXISTS idx_answer_events_user_question ON answer_events(user_id, question_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_review_user_due ON review_state(user_id, due_at);
            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
            INSERT INTO schema_meta(key, value) VALUES ('version', '3') ON CONFLICT(key) DO UPDATE SET value=excluded.value;
            """
        )


def _add_column(db: sqlite3.Connection, table: str, definition: str) -> None:
    column = definition.split()[0]
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def _ensure_review_state_v3(db: sqlite3.Connection) -> None:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(review_state)").fetchall()}
    if "user_id" in columns:
        return
    db.execute("ALTER TABLE review_state RENAME TO review_state_legacy")
    db.executescript(
        """
        CREATE TABLE review_state (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            due_at TEXT, interval_days REAL NOT NULL, ease REAL NOT NULL,
            repetitions INTEGER NOT NULL, lapses INTEGER NOT NULL, scheduler TEXT NOT NULL,
            PRIMARY KEY(user_id, question_id)
        );
        INSERT INTO review_state(user_id, workspace_id, question_id, due_at, interval_days, ease, repetitions, lapses, scheduler)
        SELECT 'local-owner', 'local-default', question_id, due_at, interval_days, ease, repetitions, lapses, scheduler
        FROM review_state_legacy;
        DROP TABLE review_state_legacy;
        """
    )
