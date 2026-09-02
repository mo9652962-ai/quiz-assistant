from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from quiz_assistant.schemas.question import Question


class AIResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_keys: list[str] = Field(default_factory=list)
    answer_texts: list[str] = Field(default_factory=list)
    reasoning_summary: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    uncertainties: list[str] = Field(default_factory=list)
    needs_human_confirmation: bool = True

    @field_validator("answer_keys")
    @classmethod
    def normalized_keys(cls, value: list[str]) -> list[str]:
        return [key.strip().upper() for key in value]


def validate_ai_result(result: AIResult, question: Question) -> tuple[bool, str | None]:
    option_map = {option.key: option.text for option in question.options}
    if len(result.answer_keys) != len(set(result.answer_keys)):
        return False, "answer_keys contains duplicates"
    if any(key not in option_map for key in result.answer_keys):
        return False, "answer_keys contains an option not present in the question"
    if question.type.value == "single_choice" and len(result.answer_keys) > 1:
        return False, "single_choice accepts at most one answer key"
    if result.answer_texts:
        expected = [option_map[key] for key in result.answer_keys]
        if result.answer_texts != expected:
            return False, "answer_texts do not map exactly to answer_keys"
    return True, None
