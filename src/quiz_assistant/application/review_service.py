from __future__ import annotations

from pathlib import Path

from quiz_assistant.infrastructure.db import connect, initialize
from quiz_assistant.infrastructure.repositories import get_review_items


def review_queue(db_path: str | Path, *, wrong: bool = False, due: bool = False, limit: int = 20):
    initialize(db_path)
    with connect(db_path) as db:
        return get_review_items(db, wrong=wrong, due=due, limit=limit)
