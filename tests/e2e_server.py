from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work" / "e2e-deps"))
sys.path.insert(0, str(ROOT / "src"))

def build_app():
    import uvicorn

    from quiz_assistant.api.app import create_app
    from quiz_assistant.application.import_service import import_questions

    db_path = ROOT / "work" / "e2e" / "quiz.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    fixture = ROOT / "tests" / "fixtures" / "sample_questions.json"
    import_questions(fixture, db_path)
    return uvicorn, create_app(db_path=db_path, session_token="e2e-session")


if __name__ == "__main__":
    uvicorn, app = build_app()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("QUIZ_E2E_PORT", "28765")),
        log_level="warning",
    )
