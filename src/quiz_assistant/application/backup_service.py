from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from quiz_assistant.infrastructure.db import initialize, is_postgres_target


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(db_path: str | Path, backup_root: str | Path | None = None) -> Path:
    if is_postgres_target(db_path):
        raise ValueError("online backup currently supports SQLite targets only")
    db_path = Path(db_path)
    initialize(db_path)
    root = Path(backup_root or db_path.parent / "backups")
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = root / stamp
    suffix = 1
    while target.exists():
        target = root / f"{stamp}-{suffix}"
        suffix += 1
    copy = target / db_path.name
    target.mkdir()
    try:
        _online_backup(db_path, copy)
        manifest = {
            "format_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "files": {copy.name: sha256(copy)},
        }
        (target / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return target


def restore_backup(backup_dir: str | Path, db_path: str | Path, *, force: bool = False) -> None:
    backup_dir, db_path = Path(backup_dir), Path(db_path)
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValueError("backup manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    db_name = db_path.name
    source = backup_dir / db_name
    if (
        db_name not in manifest.get("files", {})
        or not source.exists()
        or sha256(source) != manifest["files"][db_name]
    ):
        raise ValueError("backup hash validation failed")
    _assert_integrity(source)
    if db_path.exists() and not force:
        raise FileExistsError("destination exists; pass force=True to restore")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{db_path.name}.", suffix=".restore.tmp", dir=db_path.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        _online_backup(source, temporary)
        temporary.replace(db_path)
    finally:
        temporary.unlink(missing_ok=True)


def _assert_integrity(database: sqlite3.Connection | Path) -> None:
    try:
        if isinstance(database, Path):
            with sqlite3.connect(database) as connection:
                result = connection.execute("PRAGMA integrity_check").fetchone()[0]
        else:
            result = database.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        raise ValueError("backup integrity check failed") from exc
    if result != "ok":
        raise ValueError("backup integrity check failed")


def _online_backup(source: Path, destination: Path) -> None:
    source_db = sqlite3.connect(source)
    destination_db = sqlite3.connect(destination)
    try:
        source_db.backup(destination_db)
        _assert_integrity(destination_db)
        destination_db.commit()
    finally:
        destination_db.close()
        source_db.close()
