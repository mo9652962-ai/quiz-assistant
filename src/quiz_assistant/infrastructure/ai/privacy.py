from __future__ import annotations

import re

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_API_KEY = re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]+\b")
_WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\[^\s\"']+")
_POSIX_PATH = re.compile(r"(?<!\w)/(?:Users|home|private|tmp)/[^\s\"']+")


def redact_provider_text(value: str) -> str:
    """Remove common credentials, contact identifiers, and local paths."""
    value = _BEARER.sub("Bearer [REDACTED]", value)
    value = _API_KEY.sub("[REDACTED_KEY]", value)
    value = _EMAIL.sub("[REDACTED_EMAIL]", value)
    value = _WINDOWS_PATH.sub("[REDACTED_PATH]", value)
    return _POSIX_PATH.sub("[REDACTED_PATH]", value)
