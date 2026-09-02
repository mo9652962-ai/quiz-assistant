from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from quiz_assistant.infrastructure.db import initialize


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(db_path: str | Path, backup_root: str | Path | None = None) -> Path:
    db_path = Path(db_path)
    initialize(db_path)
    root = Path(backup_root or db_path.parent / "backups")
    root.mkdir(parents=True, exist_ok=True)
    target = root / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target.mkdir()
    copy = target / db_path.name
    shutil.copy2(db_path, copy)
    manifest = {
        "format_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "files": {copy.name: sha256(copy)},
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
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
    if db_path.exists() and not force:
        raise FileExistsError("destination exists; pass force=True to restore")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = db_path.with_suffix(db_path.suffix + ".restore.tmp")
    shutil.copy2(source, temporary)
    temporary.replace(db_path)
