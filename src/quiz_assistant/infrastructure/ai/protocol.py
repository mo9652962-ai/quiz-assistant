from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol

from quiz_assistant.schemas.question import Question


@dataclass(frozen=True)
class SolveRequest:
    question: Question
    context: str | None = None


@dataclass(frozen=True)
class Candidate:
    key: str
    text: str


@dataclass(frozen=True)
class ProviderResult:
    candidates: list[Candidate] = field(default_factory=list)
    explanation: str | None = None
    confidence: float | None = None
    citations: list[str] = field(default_factory=list)
    raw_response_hash: str = ""


class AnswerProvider(Protocol):
    async def solve(self, request: SolveRequest) -> ProviderResult: ...


def request_hash(request: SolveRequest) -> str:
    return hashlib.sha256(request.question.model_dump_json().encode("utf-8")).hexdigest()
