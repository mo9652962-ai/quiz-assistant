from datetime import UTC, datetime

from quiz_assistant.infrastructure.db import is_postgres_target
from quiz_assistant.infrastructure.postgres import PostgresConnection, adapt_sql


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return {"name": "demo", "created_at": datetime(2026, 9, 2, tzinfo=UTC)}

    def fetchall(self):
        return []

    def close(self):
        return None


class FakeConnection:
    def __init__(self):
        self.raw_cursor = FakeCursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.raw_cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_database_target_detects_postgres_urls_without_treating_them_as_paths():
    assert is_postgres_target("postgresql://quiz@localhost/quiz") is True
    assert is_postgres_target("data/quiz.db") is False


def test_postgres_connection_adapts_existing_repository_sql_and_rows():
    connection = FakeConnection()
    db = PostgresConnection(connection)

    row = db.execute(
        "INSERT OR IGNORE INTO tags(name) VALUES (?)", ("demo",)
    ).fetchone()

    assert adapt_sql("SELECT * FROM tags WHERE name = ?") == "SELECT * FROM tags WHERE name = %s"
    assert connection.raw_cursor.calls[0] == (
        "INSERT INTO tags(name) VALUES (%s) ON CONFLICT DO NOTHING",
        ("demo",),
    )
    assert row["name"] == "demo"
    assert row[0] == "demo"
    assert row["created_at"] == "2026-09-02T00:00:00+00:00"
