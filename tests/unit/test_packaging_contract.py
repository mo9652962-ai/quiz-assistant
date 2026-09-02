from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_project_has_versioned_uv_lockfile():
    lockfile = ROOT / "uv.lock"

    assert lockfile.is_file()
    assert "version = 1" in lockfile.read_text(encoding="utf-8")


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
    assert "LOCALAPPDATA" in launcher
    assert "QuizAssistant" in launcher
    assert '"data"' in launcher
    assert "onedir" in build.lower()
    assert "LOCALAPPDATA" in run
    assert "QUIZ_DB_PATH" in run
    assert "_internal\\frontend\\dist" in run
    assert "Bundled frontend/dist/index.html not found" in run
    assert "127.0.0.1" in run
    assert "Remove-Item" not in run


def test_windows_operations_document_recovery_and_port_diagnostics():
    operations = (ROOT / "docs" / "windows-operations.md").read_text(encoding="utf-8")

    assert "备份" in operations
    assert "回滚" in operations
    assert "端口" in operations
    assert "integrity_check" in operations
    assert "127.0.0.1" in operations


def test_windows_release_scripts_create_and_verify_hash_manifest():
    release = (ROOT / "packaging" / "release.ps1").read_text(encoding="utf-8")
    verify = (ROOT / "packaging" / "verify-release.ps1").read_text(encoding="utf-8")
    operations = (ROOT / "docs" / "windows-operations.md").read_text(encoding="utf-8")

    assert "Get-FileHash" in release
    assert "release-manifest.json" in release
    assert "ConvertTo-Json" in release
    assert "quiz-assistant.exe" in release
    assert "Set-AuthenticodeSignature" in release
    assert "CertificateThumbprint" in release
    assert "Get-FileHash" in verify
    assert "ConvertFrom-Json" in verify
    assert "release-manifest.json" in verify
    assert "SHA-256" in operations
    assert "verify-release.ps1" in operations
    assert "Remove-Item" not in release
    assert "Remove-Item" not in verify


def test_postgres_staging_smoke_requires_database_url_and_explicit_write_acknowledgement():
    smoke = (ROOT / "scripts" / "run_postgres_staging_smoke.ps1").read_text(encoding="utf-8")

    assert "QUIZ_DATABASE_URL" in smoke
    assert '"postgres", "postgresql"' in smoke
    assert "ConfirmStagingWrite" in smoke
    assert "postgres-migrate" in smoke
    assert "postgres-import-snapshot" in smoke
    assert "--locked" in smoke
    assert "PostgreSQL staging" in smoke
    assert "$env:QUIZ_DATABASE_URL" not in smoke.split("Write-Output")[-1]


def test_windows_installer_is_user_facing_and_keeps_user_data_on_uninstall():
    installer = (ROOT / "packaging" / "quiz-assistant.iss").read_text(encoding="utf-8")
    build = (ROOT / "packaging" / "build-installer.ps1").read_text(encoding="utf-8")

    assert "DefaultDirName={autopf}\\QuizAssistant" in installer
    assert "PrivilegesRequired=admin" in installer
    assert "recursesubdirs" in installer
    assert "{localappdata}" not in installer
    assert "[UninstallDelete]" not in installer
    assert "ISCC.exe" in build or '"iscc"' in build
    assert "Set-AuthenticodeSignature" in build
    assert "Get-AuthenticodeSignature" in build


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
