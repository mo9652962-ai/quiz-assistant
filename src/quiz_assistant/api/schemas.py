from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class MembershipResponse(BaseModel):
    workspace_id: str
    workspace_name: str
    role: str


class UserResponse(BaseModel):
    id: str
    username: str
    global_role: str
    workspace_id: str
    workspace_name: str
    workspace_role: str
    memberships: list[MembershipResponse]


class LoginResponse(BaseModel):
    user: UserResponse


class PublicOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    text: str


class PublicQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    bank: str
    version: int
    type: str
    stem: str
    options: list[PublicOption]
    explanation: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: str


class BankSummary(BaseModel):
    name: str
    version: int
    question_count: int
    active_count: int


class BanksResponse(BaseModel):
    items: list[BankSummary]
    total: int


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=20_000)
    options: list[str] = Field(default_factory=list, max_length=20)
    top_k: int = Field(default=5, ge=1, le=20)
    bank: str | None = Field(default=None, max_length=200)
    reveal: Literal["none", "candidate"] = "candidate"


class AlternativeMatch(BaseModel):
    question_id: str
    score: float
    method: str


class MatchResponse(BaseModel):
    status: str
    question_id: str | None
    answer_keys: list[str]
    answer_texts: list[str]
    method: str
    score: float
    evidence: list[str]
    normalizer_version: str
    alternatives: list[AlternativeMatch]
    auto_answerable: bool


class PracticeSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bank: str | None = Field(default=None, max_length=200)
    tag: str | None = Field(default=None, max_length=200)
    count: int = Field(default=10, ge=1, le=100)
    mode: Literal["practice"] = "practice"


class PracticeSessionResponse(BaseModel):
    id: str
    mode: str
    started_at: datetime
    questions: list[PublicQuestion]
    answer_reveal: Literal["after_user_confirmation"] = "after_user_confirmation"


class AnswerSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1, max_length=200)
    answer: str = Field(min_length=1, max_length=2_000)
    elapsed_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    reveal_answer: bool = False


class ReviewStateResponse(BaseModel):
    due_at: datetime | None
    repetitions: int
    interval_days: float
    ease: float
    lapses: int


class AnswerResponse(BaseModel):
    question_id: str
    is_correct: bool
    answer_event_id: int
    review_state: ReviewStateResponse
    answer_revealed: bool
    correct_keys: list[str] | None = None
    explanation: str | None = None


class ReviewItemResponse(BaseModel):
    question: PublicQuestion
    due_at: datetime | None
    interval_days: float
    ease: float
    repetitions: int
    lapses: int


class ReviewsResponse(BaseModel):
    items: list[ReviewItemResponse]
    total: int


class RejectedImport(BaseModel):
    row_number: int
    error: str
    raw: dict


class ImportResponse(BaseModel):
    source_name: str
    dry_run: bool
    total: int
    imported: int
    skipped_duplicate: int
    rejected_count: int
    rejected: list[RejectedImport]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    schema_version: int
    ai_enabled: bool


class BackupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["create", "restore"]
    backup_id: str | None = Field(default=None, pattern=r"^[0-9TZ-]+$")
    confirm: str | None = None
    force: bool = False


class BackupResponse(BaseModel):
    action: Literal["create", "restore"]
    backup_id: str
    schema_version: int
    sha256: str | None = None
    verified: bool
