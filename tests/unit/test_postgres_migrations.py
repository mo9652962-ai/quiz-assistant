import pytest

from quiz_assistant.infrastructure.postgres import apply_postgres_migrations, load_migrations


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, sql, params=None):
        self.connection.executed.append((sql, params))
        if sql.startswith("SELECT version FROM schema_migrations"):
            self.rows = [
                {"version": version} if self.connection.dict_rows else (version,)
                for version in self.connection.applied
            ]
        elif sql.startswith("INSERT INTO schema_migrations"):
            self.connection.applied.add(params[0])
        if self.connection.fail_on_migration and "CREATE TABLE workspaces" in sql:
            raise RuntimeError("migration failed")

    def fetchall(self):
        return self.rows

    def close(self):
        return None


class FakeConnection:
    def __init__(self, fail_on_migration=False, dict_rows=False):
        self.applied = set()
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_on_migration = fail_on_migration
        self.dict_rows = dict_rows

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_postgres_migration_is_idempotent_and_contains_workspace_scope():
    connection = FakeConnection()

    first = apply_postgres_migrations(connection)
    second = apply_postgres_migrations(connection)

    assert first.applied == ["001_initial"]
    assert second.applied == []
    assert connection.commits == 2
    migration_sql = load_migrations()[0].sql
    assert "workspace_id" in migration_sql
    assert "CREATE TABLE workspaces" in migration_sql
    assert "CREATE TABLE sessions" in migration_sql


def test_postgres_migration_rolls_back_when_a_migration_fails():
    connection = FakeConnection(fail_on_migration=True)

    with pytest.raises(RuntimeError, match="migration failed"):
        apply_postgres_migrations(connection)

    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.applied == set()


def test_postgres_migration_accepts_dict_rows_from_psycopg_row_factory():
    connection = FakeConnection(dict_rows=True)

    apply_postgres_migrations(connection)
    apply_postgres_migrations(connection)

    assert connection.commits == 2
