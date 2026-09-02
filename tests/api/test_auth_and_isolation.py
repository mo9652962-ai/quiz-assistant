from pathlib import Path

from fastapi.testclient import TestClient

from quiz_assistant.api.app import create_app
from quiz_assistant.infrastructure.db import connect, initialize
from quiz_assistant.infrastructure.passwords import hash_password


def test_login_me_and_logout_use_revocable_server_session(tmp_path: Path):
    db_path = tmp_path / "quiz.db"
    client = TestClient(create_app(db_path=db_path, auth_mode="accounts"))

    login = client.post(
        "/api/auth/login",
        json={"username": "local-owner", "password": "local-owner"},
    )
    assert login.status_code == 200
    assert login.cookies.get("quiz_session")
    assert login.json()["user"]["id"] == "local-owner"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["memberships"][0]["workspace_id"] == "local-default"

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    with connect(db_path) as db:
        password_hash = db.execute(
            "SELECT password_hash FROM users WHERE id = 'local-owner'"
        ).fetchone()[0]
    assert password_hash != "local-owner"
    assert password_hash.startswith("$argon2")


def test_workspace_membership_limits_banks_to_current_workspace(tmp_path: Path):
    db_path = tmp_path / "quiz.db"
    initialize(db_path)
    with connect(db_path) as db:
        db.execute(
            "INSERT INTO workspaces(id, name, created_at) VALUES ('other', 'Other', '2026-09-02')"
        )
        db.execute(
            "INSERT INTO users(id, username, password_hash, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("other-user", "other-user", "not-a-real-hash", "active", "2026-09-02"),
        )
        db.execute(
            "INSERT INTO workspace_memberships(workspace_id, user_id, role) VALUES (?, ?, ?)",
            ("other", "other-user", "owner"),
        )
    client = TestClient(create_app(db_path=db_path, auth_mode="accounts"))

    login = client.post(
        "/api/auth/login",
        json={"username": "other-user", "password": "not-a-real-hash"},
    )
    assert login.status_code == 401


def test_authenticated_banks_are_scoped_to_the_active_workspace(tmp_path: Path):
    db_path = tmp_path / "quiz.db"
    initialize(db_path)
    with connect(db_path) as db:
        db.execute(
            "INSERT INTO workspaces(id, name, created_at) VALUES ('other', 'Other', '2026-09-02')"
        )
        db.execute(
            "INSERT INTO users(id, username, password_hash, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("other-user", "other-user", hash_password("other-password"), "active", "2026-09-02"),
        )
        db.execute(
            "INSERT INTO workspace_memberships(workspace_id, user_id, role) VALUES (?, ?, ?)",
            ("other", "other-user", "owner"),
        )
        db.execute(
            "INSERT INTO question_banks(name, workspace_id, created_at) VALUES (?, ?, ?)",
            ("local-bank", "local-default", "2026-09-02"),
        )
        db.execute(
            "INSERT INTO question_banks(name, workspace_id, created_at) VALUES (?, ?, ?)",
            ("other-bank", "other", "2026-09-02"),
        )

    other_client = TestClient(create_app(db_path=db_path, auth_mode="accounts"))
    assert other_client.post(
        "/api/auth/login",
        json={"username": "other-user", "password": "other-password"},
    ).status_code == 200
    assert [item["name"] for item in other_client.get("/api/banks").json()["items"]] == [
        "other-bank"
    ]

    local_client = TestClient(create_app(db_path=db_path, auth_mode="accounts"))
    assert local_client.post(
        "/api/auth/login",
        json={"username": "local-owner", "password": "local-owner"},
    ).status_code == 200
    assert [item["name"] for item in local_client.get("/api/banks").json()["items"]] == [
        "local-bank"
    ]
