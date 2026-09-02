from __future__ import annotations

import json
from pathlib import Path

from quiz_assistant.domain.scheduler import ScheduleState, schedule_review
from quiz_assistant.infrastructure.db import connect, initialize
from quiz_assistant.infrastructure.repositories import (
    create_session,
    get_question,
    list_questions,
    record_answer,
)


def start_practice(
    db_path: str | Path, *, bank: str | None = None, tag: str | None = None, count: int = 10
) -> list:
    initialize(db_path)
    with connect(db_path) as db:
        return list_questions(db, bank=bank, tag=tag)[: max(0, count)]


def submit_answer(
    db_path: str | Path,
    question_id: str,
    user_answer: str,
    *,
    session_id: str | None = None,
    elapsed_ms: int | None = None,
    method: str | None = "practice",
    confidence: float | None = None,
) -> tuple[bool, str]:
    initialize(db_path)
    with connect(db_path) as db:
        question = get_question(db, question_id)
        if question is None:
            raise ValueError(f"question not found: {question_id}")
        session_id = session_id or create_session(
            db, "practice", json.dumps({"question_id": question_id})
        )
        correct = record_answer(
            db, session_id, question, user_answer, method, confidence, elapsed_ms
        )
        previous_row = db.execute(
            "SELECT due_at, interval_days, ease, repetitions, lapses FROM review_state WHERE question_id = ?",
            (question_id,),
        ).fetchone()
        previous = (
            ScheduleState(
                previous_row["due_at"],
                previous_row["interval_days"],
                previous_row["ease"],
                previous_row["repetitions"],
                previous_row["lapses"],
            )
            if previous_row
            else None
        )
        next_state = schedule_review(previous, 5 if correct else 1)
        db.execute(
            "INSERT INTO review_state(question_id, due_at, interval_days, ease, repetitions, lapses, scheduler) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(question_id) DO UPDATE SET due_at=excluded.due_at, interval_days=excluded.interval_days, ease=excluded.ease, repetitions=excluded.repetitions, lapses=excluded.lapses, scheduler=excluded.scheduler",
            (
                question_id,
                next_state.due_at.isoformat(),
                next_state.interval_days,
                next_state.ease,
                next_state.repetitions,
                next_state.lapses,
                "sm2-lite",
            ),
        )
    return correct, session_id
