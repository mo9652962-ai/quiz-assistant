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
    from quiz_assistant.server import app

    uvicorn.run(
        app,
        host=os.getenv("QUIZ_REMOTE_HOST", "127.0.0.1"),
        port=int(os.getenv("QUIZ_REMOTE_PORT", "8765")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
