from __future__ import annotations

import re
from dataclasses import dataclass
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
        applied_versions = {row[0] for row in cursor.fetchall()}
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
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL support requires the optional 'remote' dependency: psycopg[binary]"
        ) from exc
    return psycopg.connect(database_url, autocommit=False)


def migrate_postgres_url(database_url: str, directory: str | Path | None = None) -> MigrationReport:
    connection = connect_postgres(database_url)
    try:
        return apply_postgres_migrations(connection, directory)
    finally:
        connection.close()
