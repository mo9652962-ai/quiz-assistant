from pathlib import Path

from quiz_assistant.application.import_service import import_questions
from quiz_assistant.infrastructure.postgres import import_sqlite_snapshot_to_postgres
from quiz_assistant.infrastructure.sqlite_snapshot import export_sqlite_snapshot


class RecordingCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []
        self.rowcount = 1

    def execute(self, sql, params=None):
        self.connection.executed.append((sql, params))
        if sql.startswith("SELECT version FROM schema_migrations"):
            self.rows = [(version,) for version in self.connection.applied]
        elif sql.startswith("INSERT INTO schema_migrations"):
            self.connection.applied.add(params[0])

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return None

    def close(self):
        return None


class RecordingConnection:
    def __init__(self):
        self.applied = set()
        self.executed = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return RecordingCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_snapshot_can_be_loaded_into_postgres_target_without_sessions(tmp_path: Path):
    source_db = tmp_path / "source.db"
    snapshot = tmp_path / "snapshot.json"
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_questions.json"
    import_questions(fixture, source_db)
    export_sqlite_snapshot(source_db, snapshot)
    connection = RecordingConnection()

    report = import_sqlite_snapshot_to_postgres(connection, snapshot)

    assert report.question_count == 3
    inserts = [sql for sql, _ in connection.executed if sql.startswith("INSERT INTO")]
    assert any("questions" in sql for sql in inserts)
    assert all("?" not in sql for sql in inserts)
    assert connection.commits == 2
    assert connection.rollbacks == 0
