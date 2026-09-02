from __future__ import annotations

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

_PASSWORD_HASH = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _PASSWORD_HASH.verify(password, password_hash)
    except (UnknownHashError, ValueError, TypeError):
        return False
