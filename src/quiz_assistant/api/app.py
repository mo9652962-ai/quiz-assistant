from __future__ import annotations

import json
import secrets
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from quiz_assistant.api.schemas import (
    AlternativeMatch,
    AnswerResponse,
    AnswerSubmission,
    BackupRequest,
    BackupResponse,
    BanksResponse,
    BankSummary,
    HealthResponse,
    ImportResponse,
    MatchResponse,
    PracticeSessionRequest,
    PracticeSessionResponse,
    PublicOption,
    PublicQuestion,
    QueryRequest,
    ReviewItemResponse,
    ReviewsResponse,
    ReviewStateResponse,
)
from quiz_assistant.application.backup_service import create_backup, restore_backup, sha256
from quiz_assistant.application.import_service import import_questions
from quiz_assistant.application.practice_service import start_practice, submit_answer
from quiz_assistant.application.query_service import query_questions
from quiz_assistant.application.review_service import review_queue
from quiz_assistant.infrastructure.db import SCHEMA_VERSION, connect, initialize
from quiz_assistant.infrastructure.repositories import create_session


def _public_question(question, *, include_explanation: bool = False) -> PublicQuestion:
    return PublicQuestion(
        id=question.id,
        bank=question.bank,
        version=question.version,
        type=question.type.value,
        stem=question.stem,
        options=[PublicOption(key=item.key, text=item.text) for item in question.options],
        explanation=question.explanation if include_explanation else None,
        tags=question.tags,
        status=question.status.value,
    )


def _session_dependency(x_quiz_session: str | None = Header(default=None, alias="X-Quiz-Session")):
    return x_quiz_session


def create_app(
    db_path: str | Path = "data/quiz.db",
    *,
    session_token: str | None = None,
    allow_origins: list[str] | None = None,
    ai_enabled: bool = False,
) -> FastAPI:
    db_path = Path(db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize(app.state.db_path)
        yield

    app = FastAPI(title="Quiz Assistant API", version="0.1.0", lifespan=lifespan)
    app.state.db_path = db_path
    app.state.session_token = session_token or secrets.token_urlsafe(32)
    app.state.ai_enabled = ai_enabled
    app.state.backup_root = db_path.parent / "backups"

    origins = allow_origins or []
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Quiz-Session"],
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request, exc):
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": "request validation failed",
                "details": exc.errors(),
            },
        )

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        initialize(app.state.db_path)
        return HealthResponse(
            status="ok", schema_version=SCHEMA_VERSION, ai_enabled=app.state.ai_enabled
        )

    @app.get("/api/banks", response_model=BanksResponse)
    def banks(_: str | None = Depends(_session_dependency)) -> BanksResponse:
        _check_session(app, _)
        initialize(app.state.db_path)
        with connect(app.state.db_path) as db:
            rows = db.execute(
                """
                SELECT b.name, b.version,
                       COUNT(q.id) AS question_count,
                       SUM(CASE WHEN q.status = 'active' THEN 1 ELSE 0 END) AS active_count
                FROM question_banks b
                LEFT JOIN questions q ON q.bank_id = b.id
                GROUP BY b.id ORDER BY b.name
                """
            ).fetchall()
        items = [
            BankSummary(
                name=row["name"],
                version=row["version"],
                question_count=row["question_count"],
                active_count=row["active_count"] or 0,
            )
            for row in rows
        ]
        return BanksResponse(items=items, total=len(items))

    @app.post("/api/queries", response_model=MatchResponse)
    def queries(
        payload: QueryRequest, _: str | None = Depends(_session_dependency)
    ) -> MatchResponse:
        _check_session(app, _)
        result = query_questions(
            app.state.db_path, payload.text, payload.options, payload.top_k, payload.bank
        )
        reveal = payload.reveal == "candidate" and result.status == "high_confidence"
        return MatchResponse(
            status=result.status,
            question_id=result.question_id,
            answer_keys=result.answer_keys if reveal else [],
            answer_texts=result.answer_texts if reveal else [],
            method=result.method,
            score=result.score,
            evidence=result.evidence,
            normalizer_version=result.normalizer_version,
            alternatives=[
                AlternativeMatch(
                    question_id=item.question.id, score=item.score, method=item.method
                )
                for item in result.alternatives
            ],
        )

    @app.post("/api/practice/sessions", response_model=PracticeSessionResponse, status_code=201)
    def practice_session(
        payload: PracticeSessionRequest, _: str | None = Depends(_session_dependency)
    ) -> PracticeSessionResponse:
        _check_session(app, _)
        questions = start_practice(
            app.state.db_path, bank=payload.bank, tag=payload.tag, count=payload.count
        )
        initialize(app.state.db_path)
        with connect(app.state.db_path) as db:
            session_id = create_session(
                db, payload.mode, json.dumps({"bank": payload.bank, "tag": payload.tag})
            )
            started = db.execute(
                "SELECT started_at FROM practice_sessions WHERE id = ?", (session_id,)
            ).fetchone()[0]
        return PracticeSessionResponse(
            id=session_id,
            mode=payload.mode,
            started_at=datetime.fromisoformat(started),
            questions=[_public_question(question) for question in questions],
        )

    @app.post(
        "/api/practice/sessions/{session_id}/answers",
        response_model=AnswerResponse,
    )
    def practice_answer(
        session_id: str,
        payload: AnswerSubmission,
        _: str | None = Depends(_session_dependency),
    ) -> AnswerResponse:
        _check_session(app, _)
        initialize(app.state.db_path)
        with connect(app.state.db_path) as db:
            if not db.execute(
                "SELECT 1 FROM practice_sessions WHERE id = ?", (session_id,)
            ).fetchone():
                raise HTTPException(status_code=404, detail="practice session not found")
        correct, _ = submit_answer(
            app.state.db_path,
            payload.question_id,
            payload.answer,
            session_id=session_id,
            elapsed_ms=payload.elapsed_ms,
        )
        with connect(app.state.db_path) as db:
            event = db.execute(
                "SELECT id FROM answer_events WHERE session_id = ? AND question_id = ? ORDER BY id DESC LIMIT 1",
                (session_id, payload.question_id),
            ).fetchone()
            state = db.execute(
                "SELECT due_at, interval_days, ease, repetitions, lapses FROM review_state WHERE question_id = ?",
                (payload.question_id,),
            ).fetchone()
            question = db.execute(
                "SELECT * FROM questions WHERE id = ?", (payload.question_id,)
            ).fetchone()
        if not event or not state or not question:
            raise HTTPException(status_code=500, detail="answer event was not persisted")
        revealed = payload.reveal_answer
        correct_keys = None
        explanation = None
        if revealed:
            with connect(app.state.db_path) as db:
                stored = db.execute(
                    "SELECT option_key FROM options WHERE question_id = ? AND is_correct = 1 ORDER BY id",
                    (payload.question_id,),
                ).fetchall()
            correct_keys = [row[0] for row in stored]
            explanation = question["explanation"]
        return AnswerResponse(
            question_id=payload.question_id,
            is_correct=correct,
            answer_event_id=event[0],
            review_state=ReviewStateResponse(
                due_at=datetime.fromisoformat(state[0]) if state[0] else None,
                interval_days=state[1],
                ease=state[2],
                repetitions=state[3],
                lapses=state[4],
            ),
            answer_revealed=revealed,
            correct_keys=correct_keys,
            explanation=explanation,
        )

    @app.get("/api/reviews", response_model=ReviewsResponse)
    def reviews(
        wrong: bool = Query(False),
        due: bool = Query(False),
        limit: int = Query(20, ge=1, le=100),
        _: str | None = Depends(_session_dependency),
    ) -> ReviewsResponse:
        _check_session(app, _)
        items = review_queue(app.state.db_path, wrong=wrong, due=due, limit=limit)
        return ReviewsResponse(
            items=[
                ReviewItemResponse(
                    question=_public_question(item.question),
                    due_at=item.due_at,
                    interval_days=item.interval_days,
                    ease=item.ease,
                    repetitions=item.repetitions,
                    lapses=item.lapses,
                )
                for item in items
            ],
            total=len(items),
        )

    @app.post("/api/imports", response_model=ImportResponse)
    async def imports(
        file: UploadFile = File(...),  # noqa: B008 - FastAPI dependency declaration
        dry_run: bool = Form(False),
        _: str | None = Depends(_session_dependency),
    ) -> ImportResponse:
        _check_session(app, _)
        raw = await file.read()
        if len(raw) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="upload exceeds 20 MiB limit")
        suffix = Path(file.filename or "upload.json").suffix.lower()
        if suffix not in {".json", ".jsonl", ".csv"}:
            raise HTTPException(status_code=400, detail="only JSON, JSONL, and CSV are supported")
        raw_root = app.state.db_path.parent / "raw"
        raw_root.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=suffix, dir=raw_root, delete=False
            ) as handle:
                handle.write(raw)
                temporary = Path(handle.name)
            report = import_questions(temporary, app.state.db_path, dry_run=dry_run)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        return ImportResponse(
            source_name=file.filename or "upload",
            dry_run=report.dry_run,
            total=report.total,
            imported=report.imported,
            skipped_duplicate=report.skipped_duplicate,
            rejected_count=report.rejected_count,
            rejected=[item.model_dump() for item in report.rejected],
        )

    @app.post("/api/backups", response_model=BackupResponse)
    def backups(
        payload: BackupRequest, _: str | None = Depends(_session_dependency)
    ) -> BackupResponse:
        _check_session(app, _)
        if payload.action == "create":
            target = create_backup(app.state.db_path, app.state.backup_root)
            manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
            db_name = app.state.db_path.name
            return BackupResponse(
                action="create",
                backup_id=target.name,
                schema_version=SCHEMA_VERSION,
                sha256=manifest["files"][db_name],
                verified=True,
            )
        if not payload.backup_id or payload.confirm != "RESTORE_CURRENT_DATABASE":
            raise HTTPException(status_code=403, detail="explicit restore confirmation required")
        backup_dir = (app.state.backup_root / payload.backup_id).resolve()
        if app.state.backup_root.resolve() not in backup_dir.parents:
            raise HTTPException(status_code=400, detail="invalid backup id")
        try:
            restore_backup(backup_dir, app.state.db_path, force=payload.force)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return BackupResponse(
            action="restore",
            backup_id=payload.backup_id,
            schema_version=SCHEMA_VERSION,
            sha256=sha256(app.state.db_path),
            verified=True,
        )

    return app


def _check_session(app: FastAPI, token: str | None) -> None:
    expected = app.state.session_token
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="valid local session required")
