from __future__ import annotations

from pathlib import Path

from quiz_assistant.domain.matcher import match_questions
from quiz_assistant.domain.models import MatchResult
from quiz_assistant.infrastructure.db import connect, initialize
from quiz_assistant.infrastructure.repositories import list_questions


def query_questions(
    db_path: str | Path,
    stem: str,
    options: list[str] | None = None,
    top_k: int = 5,
    bank: str | None = None,
    workspace_id: str | None = None,
) -> MatchResult:
    initialize(db_path)
    with connect(db_path) as db:
        questions = list_questions(db, bank=bank, workspace_id=workspace_id)
    return match_questions(questions, stem, options, top_k)
