"""Password hashing (stdlib scrypt) and bearer-token dependencies."""

import hashlib
import hmac
import secrets
import sqlite3

from fastapi import Depends, HTTPException, Request

from . import repo

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), **_SCRYPT)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, hex_digest = stored.split("$", 1)
    except ValueError:
        return False
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), **_SCRYPT)
    return hmac.compare_digest(digest.hex(), hex_digest)


def get_db(request: Request) -> sqlite3.Connection:
    return request.app.state.db


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):]
    return None


def require_instructor(request: Request, db: sqlite3.Connection = Depends(get_db)) -> dict:
    token = _bearer_token(request)
    row = repo.lookup_token(db, token) if token else None
    if row is None or row["kind"] != "instructor":
        raise HTTPException(status_code=401, detail="instructor authentication required")
    return {"instructor_id": row["instructor_id"]}


def require_student(request: Request, db: sqlite3.Connection = Depends(get_db)) -> dict:
    token = _bearer_token(request)
    row = repo.lookup_token(db, token) if token else None
    if row is None or row["kind"] != "student":
        raise HTTPException(status_code=401, detail="student authentication required")
    ctx = repo.get_enrollment_context(db, row["enrollment_id"])
    if ctx is None:
        raise HTTPException(status_code=401, detail="enrollment no longer exists")
    return ctx


def require_owned_class(
    class_id: int,
    me: dict = Depends(require_instructor),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    cls = repo.get_class(db, class_id)
    if cls is None or cls["instructor_id"] != me["instructor_id"]:
        raise HTTPException(status_code=404, detail="class not found")
    return cls
