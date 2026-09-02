from __future__ import annotations

import json
import secrets
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

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
    LoginRequest,
    LoginResponse,
    MatchResponse,
    MembershipResponse,
    PracticeSessionRequest,
    PracticeSessionResponse,
    PublicOption,
    PublicQuestion,
    QueryRequest,
    ReviewItemResponse,
    ReviewsResponse,
    ReviewStateResponse,
    UserResponse,
)
from quiz_assistant.application.account_service import (
    Actor,
    actor_from_session,
    authenticate_user,
    ensure_remote_owner,
    memberships,
    revoke_session,
)
from quiz_assistant.application.account_service import (
    create_session as create_account_session,
)
from quiz_assistant.application.backup_service import create_backup, restore_backup, sha256
from quiz_assistant.application.import_service import import_questions
from quiz_assistant.application.practice_service import start_practice, submit_answer
from quiz_assistant.application.query_service import query_questions
from quiz_assistant.application.review_service import review_queue
from quiz_assistant.infrastructure.db import SCHEMA_VERSION, connect, initialize
from quiz_assistant.infrastructure.repositories import create_session


class RemoteReadOnlyError(Exception):
    """Raised when a Phase C remote pilot receives a data-mutating request."""


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


def _session_dependency(
    x_quiz_session: str | None = Header(default=None, alias="X-Quiz-Session"),
    quiz_session: str | None = Cookie(default=None),
):
    return x_quiz_session or quiz_session


def create_app(
    db_path: str | Path = "data/quiz.db",
    *,
    database_url: str | None = None,
    session_token: str | None = None,
    allow_origins: list[str] | None = None,
    ai_enabled: bool = False,
    auth_mode: str = "local",
    secure_cookies: bool = False,
    remote_read_only: bool = False,
    remote_owner_username: str | None = None,
    remote_owner_password: str | None = None,
    allowed_hosts: list[str] | None = None,
) -> FastAPI:
    db_path = Path(db_path)
    db_target = database_url or db_path

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize(app.state.db_target)
        if app.state.remote_owner_username and app.state.remote_owner_password:
            ensure_remote_owner(
                app.state.db_target,
                app.state.remote_owner_username,
                app.state.remote_owner_password,
            )
        yield

    app = FastAPI(title="Quiz Assistant API", version="0.1.0", lifespan=lifespan)
    app.state.db_path = db_path
    app.state.db_target = db_target
    app.state.session_token = session_token or secrets.token_urlsafe(32)
    app.state.ai_enabled = ai_enabled
    if auth_mode not in {"local", "accounts"}:
        raise ValueError("auth_mode must be 'local' or 'accounts'")
    app.state.auth_mode = auth_mode
    app.state.secure_cookies = secure_cookies
    app.state.remote_read_only = remote_read_only
    app.state.remote_owner_username = remote_owner_username
    app.state.remote_owner_password = remote_owner_password
    app.state.backup_root = db_path.parent / "backups" if database_url is None else None

    origins = allow_origins or []
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Quiz-Session"],
        )
    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

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

    @app.exception_handler(RemoteReadOnlyError)
    async def remote_read_only_handler(request, exc):
        return JSONResponse(
            status_code=403,
            content={
                "code": "remote_read_only",
                "message": "remote read-only pilot does not allow data writes",
            },
        )

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        initialize(app.state.db_target)
        return HealthResponse(
            status="ok", schema_version=SCHEMA_VERSION, ai_enabled=app.state.ai_enabled
        )

    @app.post("/api/auth/login", response_model=LoginResponse)
    def login(payload: LoginRequest, response: Response) -> LoginResponse:
        user = authenticate_user(app.state.db_target, payload.username, payload.password)
        if not user:
            raise HTTPException(status_code=401, detail="invalid username or password")
        token = create_account_session(app.state.db_target, user["id"])
        response.set_cookie(
            "quiz_session",
            token,
            httponly=True,
            secure=app.state.secure_cookies,
            samesite="lax",
            max_age=7 * 24 * 60 * 60,
        )
        actor = actor_from_session(app.state.db_target, token)
        if actor is None:
            raise HTTPException(status_code=500, detail="session was not persisted")
        return LoginResponse(user=_user_response(app.state.db_target, actor))

    @app.get("/api/auth/me", response_model=UserResponse)
    def me(token: str | None = Depends(_session_dependency)) -> UserResponse:
        actor = _check_session(app, token)
        return _user_response(app.state.db_target, actor)

    @app.post("/api/auth/logout", status_code=204)
    def logout(response: Response, token: str | None = Depends(_session_dependency)) -> Response:
        revoke_session(app.state.db_target, token)
        response.delete_cookie("quiz_session")
        response.status_code = 204
        return response

    @app.get("/api/banks", response_model=BanksResponse)
    def banks(token: str | None = Depends(_session_dependency)) -> BanksResponse:
        actor = _check_session(app, token)
        initialize(app.state.db_target)
        with connect(app.state.db_target) as db:
            rows = db.execute(
                """
                SELECT b.name, b.version,
                       COUNT(q.id) AS question_count,
                       SUM(CASE WHEN q.status = 'active' THEN 1 ELSE 0 END) AS active_count
                FROM question_banks b
                LEFT JOIN questions q ON q.bank_id = b.id
                WHERE b.workspace_id = ?
                GROUP BY b.id ORDER BY b.name
                """,
                (actor.workspace_id,),
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
        payload: QueryRequest, token: str | None = Depends(_session_dependency)
    ) -> MatchResponse:
        actor = _check_session(app, token)
        result = query_questions(
            app.state.db_target,
            payload.text,
            payload.options,
            payload.top_k,
            payload.bank,
            actor.workspace_id,
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
            auto_answerable=reveal and result.status == "high_confidence" and bool(result.answer_keys),
            alternatives=[
                AlternativeMatch(
                    question_id=item.question.id, score=item.score, method=item.method
                )
                for item in result.alternatives
            ],
        )

    @app.post("/api/practice/sessions", response_model=PracticeSessionResponse, status_code=201)
    def practice_session(
        payload: PracticeSessionRequest, token: str | None = Depends(_session_dependency)
    ) -> PracticeSessionResponse:
        actor = _check_session(app, token)
        _require_writable(app)
        questions = start_practice(
            app.state.db_target,
            bank=payload.bank,
            tag=payload.tag,
            count=payload.count,
            workspace_id=actor.workspace_id,
        )
        initialize(app.state.db_target)
        with connect(app.state.db_target) as db:
            session_id = create_session(
                db,
                payload.mode,
                json.dumps({"bank": payload.bank, "tag": payload.tag}),
                actor.user_id,
                actor.workspace_id,
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
        token: str | None = Depends(_session_dependency),
    ) -> AnswerResponse:
        actor = _check_session(app, token)
        _require_writable(app)
        initialize(app.state.db_target)
        with connect(app.state.db_target) as db:
            session = db.execute(
                "SELECT user_id, workspace_id FROM practice_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="practice session not found")
            if session["user_id"] != actor.user_id or session["workspace_id"] != actor.workspace_id:
                raise HTTPException(status_code=404, detail="practice session not found")
        correct, _ = submit_answer(
            app.state.db_target,
            payload.question_id,
            payload.answer,
            session_id=session_id,
            elapsed_ms=payload.elapsed_ms,
            user_id=actor.user_id,
            workspace_id=actor.workspace_id,
        )
        with connect(app.state.db_target) as db:
            event = db.execute(
                "SELECT id FROM answer_events WHERE session_id = ? AND question_id = ? ORDER BY id DESC LIMIT 1",
                (session_id, payload.question_id),
            ).fetchone()
            state = db.execute(
                "SELECT due_at, interval_days, ease, repetitions, lapses FROM review_state WHERE question_id = ? AND user_id = ? AND workspace_id = ?",
                (payload.question_id, actor.user_id, actor.workspace_id),
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
            with connect(app.state.db_target) as db:
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
        token: str | None = Depends(_session_dependency),
    ) -> ReviewsResponse:
        actor = _check_session(app, token)
        items = review_queue(
            app.state.db_target,
            wrong=wrong,
            due=due,
            limit=limit,
            user_id=actor.user_id,
            workspace_id=actor.workspace_id,
        )
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
        token: str | None = Depends(_session_dependency),
    ) -> ImportResponse:
        actor = _check_session(app, token)
        _require_writable(app)
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
            report = import_questions(
                temporary,
                app.state.db_target,
                dry_run=dry_run,
                workspace_id=actor.workspace_id,
            )
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
        payload: BackupRequest, token: str | None = Depends(_session_dependency)
    ) -> BackupResponse:
        actor = _check_session(app, token)
        _require_writable(app)
        if actor.workspace_role != "owner" and actor.global_role != "owner":
            raise HTTPException(status_code=403, detail="workspace owner permission required")
        if payload.action == "create":
            target = create_backup(app.state.db_target, app.state.backup_root)
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
            restore_backup(backup_dir, app.state.db_target, force=payload.force)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return BackupResponse(
            action="restore",
            backup_id=payload.backup_id,
            schema_version=SCHEMA_VERSION,
            sha256=sha256(app.state.db_target),
            verified=True,
        )

    return app


def _require_writable(app: FastAPI) -> None:
    if app.state.remote_read_only:
        raise RemoteReadOnlyError


def _check_session(app: FastAPI, token: str | None) -> Actor:
    if app.state.auth_mode == "accounts":
        actor = actor_from_session(app.state.db_target, token)
        if actor is None:
            raise HTTPException(status_code=401, detail="valid account session required")
        return actor
    expected = app.state.session_token
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="valid local session required")
    return Actor(
        user_id="local-owner",
        username="local-owner",
        global_role="owner",
        workspace_id="local-default",
        workspace_name="Local default",
        workspace_role="owner",
    )


def _user_response(db_path: str | Path, actor: Actor) -> UserResponse:
    return UserResponse(
        id=actor.user_id,
        username=actor.username,
        global_role=actor.global_role,
        workspace_id=actor.workspace_id,
        workspace_name=actor.workspace_name,
        workspace_role=actor.workspace_role,
        memberships=[
            MembershipResponse(
                workspace_id=item.workspace_id,
                workspace_name=item.workspace_name,
                role=item.role,
            )
            for item in memberships(db_path, actor.user_id)
        ],
    )
