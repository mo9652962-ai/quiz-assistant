from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from quiz_assistant.infrastructure.db import SCHEMA_VERSION, connect, initialize

SNAPSHOT_FORMAT = "quiz-assistant-sqlite-snapshot"
SNAPSHOT_VERSION = 1
MAX_SNAPSHOT_BYTES = 100 * 1024 * 1024

TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "workspaces": ("id", "name", "created_at"),
    "users": ("id", "username", "email", "password_hash", "status", "global_role", "created_at"),
    "workspace_memberships": ("workspace_id", "user_id", "role", "created_at"),
    "question_banks": ("id", "name", "subject", "version", "source", "created_at", "workspace_id"),
    "questions": (
        "id", "bank_id", "version", "type", "stem", "normalized_stem", "answer_kind",
        "explanation", "status", "difficulty", "source_json", "tags_json", "answer_aliases_json",
    ),
    "options": ("id", "question_id", "option_key", "text", "normalized_text", "is_correct"),
    "tags": ("id", "name"),
    "question_tags": ("question_id", "tag_id"),
    "practice_sessions": ("id", "mode", "started_at", "ended_at", "filter_json", "user_id", "workspace_id"),
    "answer_events": (
        "id", "session_id", "question_id", "question_version", "user_answer", "is_correct",
        "match_method", "confidence", "elapsed_ms", "created_at", "user_id", "workspace_id",
    ),
    "review_state": (
        "user_id", "workspace_id", "question_id", "due_at", "interval_days", "ease",
        "repetitions", "lapses", "scheduler",
    ),
    "ai_audits": (
        "id", "question_text_hash", "provider", "model", "request_json", "response_json",
        "parsed_json", "validation_status", "created_at",
    ),
}

IMPORT_ORDER = tuple(TABLE_COLUMNS)


@dataclass(frozen=True)
class SnapshotReport:
    path: Path
    table_counts: dict[str, int]
    skipped: int = 0

    @property
    def question_count(self) -> int:
        return self.table_counts.get("questions", 0)


def export_sqlite_snapshot(db_path: str | Path, output_path: str | Path) -> SnapshotReport:
    db_path = Path(db_path)
    output_path = Path(output_path)
    initialize(db_path)
    tables: dict[str, list[dict]] = {}
    with connect(db_path) as db:
        for table, columns in TABLE_COLUMNS.items():
            selected = ", ".join(columns)
            tables[table] = [dict(row) for row in db.execute(f"SELECT {selected} FROM {table}").fetchall()]

    payload = {
        "format": SNAPSHOT_FORMAT,
        "snapshot_version": SNAPSHOT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "tables": tables,
        "excluded_tables": ["sessions"],
    }
    _atomic_write_json(output_path, payload)
    return SnapshotReport(output_path, {name: len(rows) for name, rows in tables.items()})


def import_sqlite_snapshot(snapshot_path: str | Path, db_path: str | Path) -> SnapshotReport:
    snapshot_path = Path(snapshot_path)
    db_path = Path(db_path)
    payload = _read_snapshot(snapshot_path)
    tables = payload["tables"]

    initialize(db_path)
    table_counts = {name: 0 for name in TABLE_COLUMNS}
    skipped = 0
    with connect(db_path) as db:
        for table in IMPORT_ORDER:
            rows = tables.get(table, [])
            columns = TABLE_COLUMNS[table]
            placeholders = ", ".join("?" for _ in columns)
            column_sql = ", ".join(columns)
            statement = f"INSERT OR IGNORE INTO {table} ({column_sql}) VALUES ({placeholders})"
            for row in rows:
                if set(row) != set(columns):
                    raise ValueError(f"snapshot row columns do not match table {table}")
                values = tuple(row[column] for column in columns)
                cursor = db.execute(statement, values)
                if cursor.rowcount == 1:
                    table_counts[table] += 1
                else:
                    skipped += 1
    return SnapshotReport(db_path, table_counts, skipped)


def _read_snapshot(path: Path) -> dict:
    if not path.is_file():
        raise ValueError("snapshot file does not exist")
    if path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("snapshot exceeds 100 MiB limit")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("snapshot is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or payload.get("format") != SNAPSHOT_FORMAT:
        raise ValueError("invalid snapshot format")
    if payload.get("snapshot_version") != SNAPSHOT_VERSION:
        raise ValueError("unsupported snapshot version")
    if payload.get("schema_version", 0) > SCHEMA_VERSION:
        raise ValueError("snapshot schema is newer than this application")
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise TypeError("snapshot tables must be an object")
    if "sessions" in tables:
        raise ValueError("sessions are never accepted in a migration snapshot")
    unknown = set(tables) - set(TABLE_COLUMNS)
    if unknown:
        raise ValueError(f"snapshot contains unsupported tables: {', '.join(sorted(unknown))}")
    for table, rows in tables.items():
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError(f"snapshot table {table} must contain row objects")
    return payload


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
