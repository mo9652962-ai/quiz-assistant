from typer.testing import CliRunner

from quiz_assistant.cli import app


def test_typer_help_keeps_core_commands_visible():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("init", "import", "search", "answer", "practice", "review", "export", "backup"):
        assert command in result.stdout

