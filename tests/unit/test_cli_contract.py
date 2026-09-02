from pathlib import Path

from typer.testing import CliRunner

from quiz_assistant.application.import_service import import_questions
from quiz_assistant.cli import app


def test_typer_help_keeps_core_commands_visible():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in (
        "init", "import", "search", "answer", "practice", "review", "export", "backup",
        "snapshot-export", "snapshot-import", "postgres-migrate",
    ):
        assert command in result.stdout


def test_snapshot_cli_exports_and_imports_a_new_sqlite_database(tmp_path: Path):
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    snapshot = tmp_path / "snapshot.json"
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_questions.json"
    import_questions(fixture, source)
    runner = CliRunner()

    exported = runner.invoke(
        app, ["snapshot-export", "--db", str(source), "--out", str(snapshot)]
    )
    assert exported.exit_code == 0, exported.stdout

    imported = runner.invoke(
        app, ["snapshot-import", "--db", str(target), "--source", str(snapshot)]
    )
    assert imported.exit_code == 0, imported.stdout
