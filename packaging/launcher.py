from __future__ import annotations

import os
import sys

import uvicorn


def main() -> None:
    if getattr(sys, "frozen", False):
        bundle_root = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        os.environ.setdefault(
            "QUIZ_FRONTEND_DIST", os.path.join(bundle_root, "frontend", "dist")
        )
        if not os.getenv("QUIZ_DATABASE_URL") and not os.getenv("QUIZ_DB_PATH"):
            local_app_data = os.getenv("LOCALAPPDATA") or os.path.dirname(sys.executable)
            data_root = os.path.join(local_app_data, "QuizAssistant", "data")
            os.makedirs(data_root, exist_ok=True)
            for child in ("backups", "exports", "raw"):
                os.makedirs(os.path.join(data_root, child), exist_ok=True)
            os.environ["QUIZ_DB_PATH"] = os.path.join(data_root, "quiz.db")
    from quiz_assistant.server import app

    uvicorn.run(
        app,
        host=os.getenv("QUIZ_REMOTE_HOST", "127.0.0.1"),
        port=int(os.getenv("QUIZ_REMOTE_PORT", "8765")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
