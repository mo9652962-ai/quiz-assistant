from pathlib import Path

from quiz_assistant.infrastructure.db import connect, initialize


def test_initialize_bootstraps_local_default_workspace_and_owner(tmp_path: Path):
    db_path = tmp_path / "quiz.db"

    initialize(db_path)

    with connect(db_path) as db:
        workspace = db.execute(
            "SELECT id, name FROM workspaces WHERE id = 'local-default'"
        ).fetchone()
        owner = db.execute(
            "SELECT id, username, status FROM users WHERE id = 'local-owner'"
        ).fetchone()
        membership = db.execute(
            "SELECT workspace_id, user_id, role FROM workspace_memberships"
        ).fetchone()

    assert tuple(workspace) == ("local-default", "Local default")
    assert tuple(owner) == ("local-owner", "local-owner", "active")
    assert tuple(membership) == ("local-default", "local-owner", "owner")


def test_remote_owner_bootstrap_is_idempotent_and_does_not_touch_local_owner(tmp_path: Path):
    from quiz_assistant.application.account_service import ensure_remote_owner
    from quiz_assistant.infrastructure.db import connect, initialize

    db_path = tmp_path / "quiz.db"
    initialize(db_path)
    ensure_remote_owner(db_path, "remote-owner", "change-me-now")
    ensure_remote_owner(db_path, "remote-owner", "ignored-on-second-run")

    with connect(db_path) as db:
        owner = db.execute(
            "SELECT username, global_role FROM users WHERE username = 'remote-owner'"
        ).fetchone()
        membership = db.execute(
            """SELECT workspace_id, role FROM workspace_memberships
               WHERE user_id = (SELECT id FROM users WHERE username = 'remote-owner')"""
        ).fetchone()
        local = db.execute(
            "SELECT username FROM users WHERE username = 'local-owner'"
        ).fetchone()

    assert tuple(owner) == ("remote-owner", "owner")
    assert tuple(membership) == ("local-default", "owner")
    assert local[0] == "local-owner"


def test_existing_question_banks_are_assigned_to_local_workspace(tmp_path: Path):
    db_path = tmp_path / "quiz.db"
    initialize(db_path)
    with connect(db_path) as db:
        db.execute(
            "INSERT INTO question_banks(name, subject, version, created_at) VALUES (?, ?, ?, ?)",
            ("demo", "English", 1, "2026-09-02T00:00:00+00:00"),
        )

    initialize(db_path)

    with connect(db_path) as db:
        workspace_id = db.execute(
            "SELECT workspace_id FROM question_banks WHERE name = 'demo'"
        ).fetchone()[0]
    assert workspace_id == "local-default"
