from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class QuestionType(StrEnum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class QuestionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "manual"
    ref: str | None = None


class Option(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=8)
    text: str = Field(min_length=1)
    correct: bool = False

    @field_validator("key")
    @classmethod
    def key_is_simple(cls, value: str) -> str:
        value = value.strip().upper()
        if not value or len(value) > 8:
            raise ValueError("option key must be non-empty and short")
        return value


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    bank: str = Field(min_length=1)
    version: int = Field(default=1, ge=1)
    type: QuestionType
    stem: str = Field(min_length=1)
    options: list[Option] = Field(default_factory=list)
    explanation: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: SourceRef = Field(default_factory=SourceRef)
    status: QuestionStatus = QuestionStatus.ACTIVE
    answer_aliases: list[str] = Field(default_factory=list)
    normalization: str | None = None

    @field_validator("id", "bank", "stem")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value

    @field_validator("tags", "answer_aliases")
    @classmethod
    def clean_list(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))

    @model_validator(mode="after")
    def validate_answer_shape(self) -> Question:
        keys = [option.key for option in self.options]
        if len(keys) != len(set(keys)):
            raise ValueError("option keys must be unique")
        if self.type is QuestionType.TRUE_FALSE:
            if len(self.options) != 2 or {key for key in keys} != {"A", "B"}:
                raise ValueError("true_false must contain A and B options")
        elif self.type is QuestionType.SINGLE_CHOICE:
            correct_count = sum(option.correct for option in self.options)
            if (
                len(self.options) < 2
                or correct_count not in {0, 1}
                or (correct_count == 0 and self.status is not QuestionStatus.DRAFT)
            ):
                raise ValueError(
                    "single_choice requires one answer, unless explicitly marked draft"
                )
        elif self.type is QuestionType.MULTIPLE_CHOICE:
            if len(self.options) < 2 or (
                not any(option.correct for option in self.options)
                and self.status is not QuestionStatus.DRAFT
            ):
                raise ValueError(
                    "multiple_choice requires an answer, unless explicitly marked draft"
                )
        elif self.type is QuestionType.SHORT_ANSWER:
            if self.options:
                raise ValueError("short_answer must not contain choice options")
            if not self.answer_aliases:
                raise ValueError("short_answer requires answer_aliases")
        return self


def question_from_payload(payload: dict[str, Any]) -> Question:
    """Convert the friendly import format into a validated Question."""
    data = dict(payload)
    q_type = data.get("type")
    if q_type == QuestionType.TRUE_FALSE:
        answer_value = data.pop("correct", None)
        if answer_value is None:
            answer_value = data.pop("correct_answer", None)
        if answer_value is None:
            correct_keys = data.pop("correct_keys", [])
            answer_value = correct_keys[0] if correct_keys else "A"
        answer = str(answer_value).strip().lower()
        is_true = answer in {"a", "true", "yes", "是", "正确"}
        data["options"] = [
            {"key": "A", "text": "True", "correct": is_true},
            {"key": "B", "text": "False", "correct": not is_true},
        ]
    if "source_ref" in data and "source" not in data:
        data["source"] = {"kind": "import", "ref": data.pop("source_ref")}
    return Question.model_validate(data)
