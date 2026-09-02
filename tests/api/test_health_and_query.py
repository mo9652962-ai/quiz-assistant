from pathlib import Path

from fastapi.testclient import TestClient

from quiz_assistant.api.app import create_app
from quiz_assistant.application.import_service import import_questions


def test_health_and_query_use_application_service(tmp_path: Path):
    db_path = tmp_path / "quiz.db"
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_questions.json"
    import_questions(fixture, db_path)
    client = TestClient(create_app(db_path=db_path, session_token="test-session"))

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    result = client.post(
        "/api/queries",
        headers={"X-Quiz-Session": "test-session"},
        json={"text": "Which sentence is grammatically correct?", "bank": "english-basic"},
    )
    assert result.status_code == 200
    assert result.json()["question_id"] == "eng-000001"


def test_query_requires_session_and_high_confidence_reveals_candidate(tmp_path: Path):
    db_path = tmp_path / "quiz.db"
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_questions.json"
    import_questions(fixture, db_path)
    client = TestClient(create_app(db_path=db_path, session_token="test-session"))

    unauthorized = client.post(
        "/api/queries", json={"text": "Which sentence is grammatically correct?"}
    )
    assert unauthorized.status_code == 401

    result = client.post(
        "/api/queries",
        headers={"X-Quiz-Session": "test-session"},
        json={"text": "Which sentence is grammatically correct?", "reveal": "candidate"},
    )
    assert result.json()["answer_keys"] == ["B"]
    assert result.json()["auto_answerable"] is True


def test_low_confidence_query_never_marks_auto_answerable(tmp_path: Path):
    db_path = tmp_path / "quiz.db"
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_questions.json"
    import_questions(fixture, db_path)
    client = TestClient(create_app(db_path=db_path, session_token="test-session"))

    result = client.post(
        "/api/queries",
        headers={"X-Quiz-Session": "test-session"},
        json={"text": "Which sentence might be correct?", "reveal": "candidate"},
    )

    assert result.status_code == 200
    assert result.json()["status"] == "needs_confirmation"
    assert result.json()["answer_keys"] == []
    assert result.json()["auto_answerable"] is False


def test_practice_payload_does_not_reveal_correct_answers(tmp_path: Path):
    db_path = tmp_path / "quiz.db"
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_questions.json"
    import_questions(fixture, db_path)
    client = TestClient(create_app(db_path=db_path, session_token="test-session"))

    response = client.post(
        "/api/practice/sessions",
        headers={"X-Quiz-Session": "test-session"},
        json={"bank": "english-basic", "count": 1},
    )
    assert response.status_code == 201
    for question in response.json()["questions"]:
        assert question["explanation"] is None
        for option in question["options"]:
            assert "correct" not in option
