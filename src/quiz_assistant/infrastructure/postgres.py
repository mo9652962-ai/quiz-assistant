from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

MIGRATION_NAME = re.compile(r"^(?P<version>\d+)_(?P<name>[a-z0-9_]+)\.sql$")
DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations" / "postgres"


@dataclass(frozen=True)
class PostgresMigration:
    version: int
    name: str
    sql: str


@dataclass(frozen=True)
class MigrationReport:
    applied: list[str]


class PostgresRow(dict):
    """Mapping row with the positional access used by the SQLite repositories."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class PostgresCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql: str, params=None):
        adapted = adapt_sql(sql)
        if params is None:
            self._cursor.execute(adapted)
        else:
            self._cursor.execute(adapted, params)
        return self

    def fetchone(self):
        return _normalize_row(self._cursor.fetchone())

    def fetchall(self):
        return [_normalize_row(row) for row in self._cursor.fetchall()]

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return None

    def close(self):
        self._cursor.close()


class PostgresConnection:
    """Small DB-API compatibility layer for the current repository code."""

    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql: str, params=None) -> PostgresCursor:
        cursor = PostgresCursor(self._connection.cursor())
        return cursor.execute(sql, params)

    def cursor(self) -> PostgresCursor:
        return PostgresCursor(self._connection.cursor())

    def executescript(self, sql: str) -> None:
        for statement in sql.split(";"):
            if statement.strip():
                self.execute(statement)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type:
                self.rollback()
            else:
                self.commit()
        finally:
            self.close()


def adapt_sql(sql: str) -> str:
    adapted = sql.replace("?", "%s")
    if re.search(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", adapted, re.IGNORECASE):
        adapted = re.sub(
            r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", adapted, flags=re.IGNORECASE
        )
        if " ON CONFLICT " not in adapted.upper():
            adapted = adapted.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return adapted


def _normalize_row(row):
    if row is None:
        return None
    if isinstance(row, Mapping):
        return PostgresRow({key: _normalize_value(value) for key, value in row.items()})
    return tuple(_normalize_value(value) for value in row)


def _normalize_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def load_migrations(directory: str | Path | None = None) -> list[PostgresMigration]:
    migration_dir = Path(directory) if directory else DEFAULT_MIGRATIONS_DIR
    migrations: list[PostgresMigration] = []
    for path in sorted(migration_dir.glob("*.sql")):
        match = MIGRATION_NAME.match(path.name)
        if not match:
            raise ValueError(f"invalid PostgreSQL migration filename: {path.name}")
        migrations.append(
            PostgresMigration(
                version=int(match.group("version")),
                name=path.stem,
                sql=path.read_text(encoding="utf-8"),
            )
        )
    versions = [migration.version for migration in migrations]
    if len(versions) != len(set(versions)):
        raise ValueError("duplicate PostgreSQL migration version")
    return sorted(migrations, key=lambda migration: migration.version)


def apply_postgres_migrations(connection, directory: str | Path | None = None) -> MigrationReport:
    """Apply ordered SQL migrations in one transaction.

    The connection is injected so a real psycopg connection and a deployment
    smoke-test connection share exactly the same migration behavior.
    """
    migrations = load_migrations(directory)
    cursor = connection.cursor()
    applied_names: list[str] = []
    try:
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                   version INTEGER PRIMARY KEY,
                   name TEXT NOT NULL,
                   applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
        applied_versions = {
            row["version"] if isinstance(row, Mapping) else row[0]
            for row in cursor.fetchall()
        }
        for migration in migrations:
            if migration.version in applied_versions:
                continue
            cursor.execute(migration.sql)
            cursor.execute(
                "INSERT INTO schema_migrations(version, name) VALUES (%s, %s)",
                (migration.version, migration.name),
            )
            applied_names.append(migration.name)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
    return MigrationReport(applied_names)


def connect_postgres(database_url: str):
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL support requires the optional 'remote' dependency: psycopg[binary]"
        ) from exc
    return psycopg.connect(database_url, autocommit=False, row_factory=dict_row)


def migrate_postgres_url(database_url: str, directory: str | Path | None = None) -> MigrationReport:
    connection = connect_postgres(database_url)
    try:
        return apply_postgres_migrations(connection, directory)
    finally:
        connection.close()


def import_sqlite_snapshot_to_postgres(
    connection, snapshot_path: str | Path, directory: str | Path | None = None
):
    """Migrate a validated SQLite snapshot into an already reachable PostgreSQL target."""
    from quiz_assistant.infrastructure.sqlite_snapshot import (
        IMPORT_ORDER,
        TABLE_COLUMNS,
        SnapshotReport,
        load_sqlite_snapshot,
    )

    payload = load_sqlite_snapshot(snapshot_path)
    apply_postgres_migrations(connection, directory)
    db = PostgresConnection(connection)
    table_counts = {name: 0 for name in TABLE_COLUMNS}
    skipped = 0
    try:
        for table in IMPORT_ORDER:
            rows = payload["tables"].get(table, [])
            columns = TABLE_COLUMNS[table]
            if table == "ai_audits":
                columns = ("workspace_id",) + columns
            placeholders = ", ".join("%s" for _ in columns)
            column_sql = ", ".join(columns)
            statement = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
            for row in rows:
                if table == "ai_audits":
                    values = (row.get("workspace_id", "local-default"),) + tuple(
                        row[column] for column in TABLE_COLUMNS[table]
                    )
                else:
                    values = tuple(row[column] for column in columns)
                cursor = db.execute(statement, values)
                if cursor.rowcount == 1:
                    table_counts[table] += 1
                else:
                    skipped += 1
        _reset_postgres_sequences(db)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return SnapshotReport(Path(snapshot_path), table_counts, skipped)


def _reset_postgres_sequences(db: PostgresConnection) -> None:
    for table in ("question_banks", "options", "tags", "answer_events", "ai_audits"):
        db.execute(
            f"""SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                       COALESCE(MAX(id), 1), MAX(id) IS NOT NULL)
                FROM {table}"""
        )
