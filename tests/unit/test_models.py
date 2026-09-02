import pytest
from pydantic import ValidationError

from quiz_assistant.schemas.question import Question


def payload(**overrides):
    value = {
        "id": "q-1",
        "bank": "demo",
        "type": "single_choice",
        "stem": "2 + 2 = ?",
        "options": [{"key": "A", "text": "3"}, {"key": "B", "text": "4", "correct": True}],
    }
    value.update(overrides)
    return value


def test_single_choice_requires_exactly_one_answer():
    with pytest.raises(ValidationError):
        Question.model_validate(
            payload(options=[{"key": "A", "text": "3"}, {"key": "B", "text": "4"}])
        )


def test_true_false_is_supported_as_two_options():
    question = Question.model_validate(
        {
            "id": "q-2",
            "bank": "demo",
            "type": "true_false",
            "stem": "Sky is blue",
            "options": [
                {"key": "A", "text": "True", "correct": True},
                {"key": "B", "text": "False"},
            ],
        }
    )
    assert [item.key for item in question.options if item.correct] == ["A"]


def test_short_answer_requires_aliases():
    with pytest.raises(ValidationError):
        Question.model_validate(
            {"id": "q-3", "bank": "demo", "type": "short_answer", "stem": "name", "options": []}
        )


def test_unanswered_choice_can_be_explicit_draft():
    question = Question.model_validate(
        payload(
            status="draft",
            options=[{"key": "A", "text": "unknown"}, {"key": "B", "text": "unknown too"}],
        )
    )
    assert question.status.value == "draft"
