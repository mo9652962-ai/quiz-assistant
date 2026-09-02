import pytest
from pydantic import ValidationError

from quiz_assistant.infrastructure.ai.local_stub import LocalStubProvider
from quiz_assistant.infrastructure.ai.protocol import SolveRequest
from quiz_assistant.schemas.ai_result import AIResult, validate_ai_result
from quiz_assistant.schemas.question import Question


def choice_question():
    return Question.model_validate(
        {
            "id": "q-1",
            "bank": "demo",
            "type": "single_choice",
            "stem": "Pick one",
            "options": [{"key": "A", "text": "one"}, {"key": "B", "text": "two", "correct": True}],
        }
    )


def test_ai_result_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        AIResult(confidence=1.1)


def test_ai_result_requires_option_consistency():
    result = AIResult(answer_keys=["C"], answer_texts=["other"])
    valid, reason = validate_ai_result(result, choice_question())
    assert not valid and "not present" in reason


def test_local_stub_is_non_networking_and_empty():
    import asyncio

    result = asyncio.run(LocalStubProvider().solve(SolveRequest(question=choice_question())))
    assert result.candidates == []
