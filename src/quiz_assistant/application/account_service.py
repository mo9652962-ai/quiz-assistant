from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from quiz_assistant.infrastructure.db import connect, initialize
from quiz_assistant.infrastructure.passwords import hash_password, verify_password

SESSION_TTL = timedelta(days=7)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Membership:
    workspace_id: str
    workspace_name: str
    role: str


@dataclass(frozen=True)
class Actor:
    user_id: str
    username: str
    global_role: str
    workspace_id: str
    workspace_name: str
    workspace_role: str


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate_user(db_path, username: str, password: str) -> dict | None:
    initialize(db_path)
    with connect(db_path) as db:
        user = db.execute(
            "SELECT id, username, global_role FROM users WHERE username = ? AND status = 'active'",
            (username,),
        ).fetchone()
        if not user:
            return None
        password_hash = db.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user["id"],)
        ).fetchone()[0]
        if not verify_password(password, password_hash):
            return None
        return dict(user)


def create_session(db_path, user_id: str, workspace_id: str | None = None) -> str:
    initialize(db_path)
    raw_token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    with connect(db_path) as db:
        if workspace_id is None:
            membership = db.execute(
                "SELECT workspace_id FROM workspace_memberships WHERE user_id = ? ORDER BY workspace_id LIMIT 1",
                (user_id,),
            ).fetchone()
            workspace_id = membership[0] if membership else None
        db.execute(
            """INSERT INTO sessions(id, user_id, workspace_id, token_hash, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                user_id,
                workspace_id,
                _token_hash(raw_token),
                now.isoformat(),
                (now + SESSION_TTL).isoformat(),
            ),
        )
    return raw_token


def revoke_session(db_path, raw_token: str | None) -> None:
    if not raw_token:
        return
    initialize(db_path)
    with connect(db_path) as db:
        db.execute(
            "UPDATE sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
            (utc_now(), _token_hash(raw_token)),
        )


def actor_from_session(db_path, raw_token: str | None) -> Actor | None:
    if not raw_token:
        return None
    initialize(db_path)
    with connect(db_path) as db:
        row = db.execute(
            """SELECT u.id AS user_id, u.username, u.global_role,
                      w.id AS workspace_id, w.name AS workspace_name, wm.role AS workspace_role
               FROM sessions s
               JOIN users u ON u.id = s.user_id
               JOIN workspace_memberships wm ON wm.user_id = u.id
               JOIN workspaces w ON w.id = wm.workspace_id
               WHERE s.token_hash = ? AND s.revoked_at IS NULL
                 AND s.expires_at > ? AND u.status = 'active'
                 AND (s.workspace_id IS NULL OR s.workspace_id = wm.workspace_id)
               ORDER BY CASE WHEN s.workspace_id = wm.workspace_id THEN 0 ELSE 1 END,
                        wm.workspace_id LIMIT 1""",
            (_token_hash(raw_token), utc_now()),
        ).fetchone()
    if not row:
        return None
    return Actor(
        user_id=row["user_id"],
        username=row["username"],
        global_role=row["global_role"],
        workspace_id=row["workspace_id"],
        workspace_name=row["workspace_name"],
        workspace_role=row["workspace_role"],
    )


def memberships(db_path, user_id: str) -> list[Membership]:
    initialize(db_path)
    with connect(db_path) as db:
        rows = db.execute(
            """SELECT wm.workspace_id, w.name, wm.role
               FROM workspace_memberships wm JOIN workspaces w ON w.id = wm.workspace_id
               WHERE wm.user_id = ? ORDER BY wm.workspace_id""",
            (user_id,),
        ).fetchall()
    return [Membership(row[0], row[1], row[2]) for row in rows]


def create_user(db_path, user_id: str, username: str, password: str, global_role: str = "user") -> None:
    initialize(db_path)
    with connect(db_path) as db:
        db.execute(
            """INSERT INTO users(id, username, password_hash, status, global_role, created_at)
               VALUES (?, ?, ?, 'active', ?, ?)""",
            (user_id, username, hash_password(password), global_role, utc_now()),
        )


def ensure_remote_owner(db_path, username: str, password: str) -> None:
    """Idempotently provision the explicitly configured remote owner.

    Existing users are never overwritten. The owner is attached to the first
    workspace created by the local-compatible schema (``local-default``).
    """
    if not username or not password or username == "local-owner":
        raise ValueError("remote owner must be explicit and must not be local-owner")
    initialize(db_path)
    with connect(db_path) as db:
        user = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if user:
            user_id = user[0]
        else:
            user_id = str(uuid.uuid4())
            db.execute(
                """INSERT INTO users(id, username, password_hash, status, global_role, created_at)
                   VALUES (?, ?, ?, 'active', 'owner', ?)""",
                (user_id, username, hash_password(password), utc_now()),
            )
        workspace = db.execute(
            "SELECT id FROM workspaces ORDER BY created_at, id LIMIT 1"
        ).fetchone()
        if not workspace:
            raise ValueError("remote owner cannot be provisioned without a workspace")
        db.execute(
            """INSERT INTO workspace_memberships(workspace_id, user_id, role, created_at)
               VALUES (?, ?, 'owner', ?)
               ON CONFLICT(workspace_id, user_id) DO UPDATE SET role = 'owner'""",
            (workspace[0], user_id, utc_now()),
        )
