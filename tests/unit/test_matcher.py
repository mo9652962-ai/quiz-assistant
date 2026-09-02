from quiz_assistant.domain.matcher import match_questions, normalize_text
from quiz_assistant.schemas.question import Question


def question(qid="q-1", stem="Which sentence is correct?"):
    return Question.model_validate(
        {
            "id": qid,
            "bank": "english",
            "type": "single_choice",
            "stem": stem,
            "options": [
                {"key": "A", "text": "He go."},
                {"key": "B", "text": "He goes.", "correct": True},
            ],
        }
    )


def test_normalizer_keeps_math_signs_and_unifies_width():
    assert normalize_text("  ２ ＋ ２ = ４  ") == "2 + 2 = 4"
    assert normalize_text("−5%") == "−5%"


def test_normalized_exact_returns_structured_result():
    result = match_questions([question()], " Which sentence is correct? ")
    assert result.status == "high_confidence"
    assert result.answer_keys == ["B"]
    assert result.method == "normalized_exact"
    assert result.evidence


def test_ambiguous_results_require_confirmation():
    result = match_questions(
        [question("q-1", "What is a good answer?"), question("q-2", "What is a bad answer?")],
        "What is an answer?",
    )
    assert result.status == "needs_confirmation"
