from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from quiz_assistant.schemas.question import Question


@dataclass(frozen=True)
class MatchCandidate:
    question: Question
    score: float
    method: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class MatchResult:
    status: str
    question_id: str | None
    answer_keys: list[str]
    answer_texts: list[str]
    method: str
    score: float
    evidence: list[str]
    alternatives: list[MatchCandidate] = field(default_factory=list)
    normalizer_version: str = "v1"


@dataclass(frozen=True)
class ReviewItem:
    question: Question
    due_at: datetime | None
    interval_days: float
    ease: float
    repetitions: int
    lapses: int
