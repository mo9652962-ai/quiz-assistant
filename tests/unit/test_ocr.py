from pathlib import Path

from quiz_assistant.infrastructure.ocr import OCRDocument, OCRQuestion, parse_ocr_text


def test_ocr_parser_extracts_question_and_inline_or_line_options_with_confidence():
    document = parse_ocr_text(
        """1. Which sentence is grammatically correct?
A. He go to school.
B. He goes to school.
C. He going to school.
D. He gone to school.
"""
    )

    assert isinstance(document, OCRDocument)
    assert len(document.questions) == 1
    question = document.questions[0]
    assert isinstance(question, OCRQuestion)
    assert question.stem == "Which sentence is grammatically correct?"
    assert [option.key for option in question.options] == ["A", "B", "C", "D"]
    assert question.status == "high_confidence"
    assert question.confidence >= 0.85
    assert question.issues == []


def test_ocr_parser_marks_incomplete_structure_for_manual_review():
    document = parse_ocr_text("1. Choose the best answer\nA. only one option\n")

    assert len(document.questions) == 1
    assert document.questions[0].status == "rejected"
    assert any("at least two options" in issue for issue in document.questions[0].issues)


def test_ocr_api_returns_batch_candidates_without_answers(tmp_path: Path, monkeypatch):
    from fastapi.testclient import TestClient

    import quiz_assistant.api.app as app_module
    from quiz_assistant.api.app import create_app
    from quiz_assistant.application.import_service import import_questions

    def fake_recognize_image(data: bytes, filename: str):
        return parse_ocr_text(
            "1. Which sentence is grammatically correct?\n"
            "A. He go to school.\nB. He goes to school.\n"
        )

    monkeypatch.setattr(app_module, "recognize_image", fake_recognize_image)
    db_path = tmp_path / "quiz.db"
    import_questions(Path(__file__).parents[1] / "fixtures" / "sample_questions.json", db_path)
    client = TestClient(create_app(db_path=db_path, session_token="test-session"))

    response = client.post(
        "/api/ocr/recognize",
        headers={"X-Quiz-Session": "test-session"},
        files=[
            (
                "files",
                ("question.png", b"not-real-image", "image/png"),
            )
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_files"] == 1
    assert payload["items"][0]["questions"][0]["status"] == "high_confidence"
    assert "answer_keys" not in payload["items"][0]["questions"][0]
    assert payload["items"][0]["questions"][0]["local_match"]["answer_keys"] == ["B"]
