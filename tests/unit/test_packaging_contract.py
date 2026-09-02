from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_windows_packaging_is_onedir_and_keeps_data_outside_install_dir():
    spec = (ROOT / "packaging" / "quiz.spec").read_text(encoding="utf-8")
    build = (ROOT / "packaging" / "build.ps1").read_text(encoding="utf-8")
    run = (ROOT / "packaging" / "run.ps1").read_text(encoding="utf-8")
    launcher = (ROOT / "packaging" / "launcher.py").read_text(encoding="utf-8")

    assert "COLLECT(" in spec
    assert "frontend/dist" in spec
    assert "migrations" in spec
    assert "from quiz_assistant.server import app" in launcher
    assert "_MEIPASS" in launcher
    assert "onedir" in build.lower()
    assert "LOCALAPPDATA" in run
    assert "QUIZ_DB_PATH" in run
    assert "127.0.0.1" in run
    assert "Remove-Item" not in run


def test_windows_operations_document_recovery_and_port_diagnostics():
    operations = (ROOT / "docs" / "windows-operations.md").read_text(encoding="utf-8")

    assert "备份" in operations
    assert "回滚" in operations
    assert "端口" in operations
    assert "integrity_check" in operations
    assert "127.0.0.1" in operations


def test_configured_frontend_serves_spa_routes_without_touching_api_routes(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from quiz_assistant.api.app import create_app

    frontend = tmp_path / "dist"
    frontend.mkdir()
    (frontend / "index.html").write_text("<html>Quiz Assistant</html>", encoding="utf-8")
    (frontend / "app.js").write_text("console.log('ok')", encoding="utf-8")
    monkeypatch.setenv("QUIZ_FRONTEND_DIST", str(frontend))

    client = TestClient(create_app(db_path=tmp_path / "quiz.db", session_token="test-session"))

    assert client.get("/").text == "<html>Quiz Assistant</html>"
    assert client.get("/ocr").text == "<html>Quiz Assistant</html>"
    assert client.get("/app.js").text == "console.log('ok')"
    assert client.get("/api/health").status_code == 200
