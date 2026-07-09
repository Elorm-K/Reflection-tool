"""Instructor-facing routes: auth, classes, roster."""

import logging
import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import repo
from ..auth import (
    get_db,
    hash_password,
    hash_reset_token,
    require_instructor,
    require_owned_class,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class RegisterBody(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)
    name: str = ""


class LoginBody(BaseModel):
    email: str
    password: str


class ClassBody(BaseModel):
    name: str = Field(min_length=1)
    term: str = ""
    timezone: str = "UTC"


class RosterEntry(BaseModel):
    student_id: str = Field(min_length=1)
    name: str = ""


class RosterBody(BaseModel):
    students: list[RosterEntry]


def _class_out(cls: dict) -> dict:
    return {k: cls[k] for k in ("id", "name", "term", "class_code", "timezone", "archived")}


@router.post("/instructor/register", status_code=201)
def register(body: RegisterBody, db: sqlite3.Connection = Depends(get_db)):
    if repo.get_instructor_by_email(db, body.email) is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    iid = repo.create_instructor(db, body.email, hash_password(body.password), body.name)
    return {"token": repo.issue_token(db, kind="instructor", instructor_id=iid)}


@router.post("/instructor/login")
def login(body: LoginBody, db: sqlite3.Connection = Depends(get_db)):
    row = repo.get_instructor_by_email(db, body.email)
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid credentials")
    return {"token": repo.issue_token(db, kind="instructor", instructor_id=row["id"])}


class ForgotPasswordBody(BaseModel):
    email: str


class ResetPasswordBody(BaseModel):
    token: str
    password: str = Field(min_length=6)


@router.post("/instructor/forgot-password")
def forgot_password(
    body: ForgotPasswordBody, request: Request,
    db: sqlite3.Connection = Depends(get_db),
):
    """Always 200 with an identical body — never reveals whether the email is
    registered. Email sending is inactive: the composed message is stored in
    email_outbox and the reset link is written to the server log for the
    pilot operator to relay. TODO before any public deployment: rate-limit
    this endpoint (nothing in the app is rate-limited yet).
    """
    row = repo.get_instructor_by_email(db, body.email)
    if row is not None:
        token = secrets.token_urlsafe(32)
        repo.create_password_reset(db, row["id"], hash_reset_token(token))
        link = f"{str(request.base_url).rstrip('/')}/reset-password?token={token}"
        repo.add_outbox_email(
            db, kind="password-reset", instructor_id=row["id"],
            recipient_email=row["email"],
            subject="Reset your GroupMatcher password",
            body=(f"A password reset was requested for this account."
                  f" The link expires in 60 minutes: {link}"),
        )
        logger.info("password reset link for %s: %s", row["email"], link)
    return {"ok": True}


@router.post("/instructor/reset-password")
def reset_password(body: ResetPasswordBody, db: sqlite3.Connection = Depends(get_db)):
    reset = repo.get_valid_password_reset(db, hash_reset_token(body.token))
    if reset is None:
        # uniform message for bad / expired / already-used tokens — no oracle
        raise HTTPException(status_code=400, detail="invalid or expired reset link")
    repo.update_instructor_password(db, reset["instructor_id"],
                                    hash_password(body.password))
    repo.mark_reset_used(db, reset["id"], reset["instructor_id"])
    repo.delete_instructor_tokens(db, reset["instructor_id"])  # force re-login everywhere
    return {"ok": True}


@router.get("/instructor/me")
def me(me: dict = Depends(require_instructor), db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        "SELECT id, email, name FROM instructors WHERE id = ?", (me["instructor_id"],)
    ).fetchone()
    return dict(row)


@router.post("/classes", status_code=201)
def create_class(
    body: ClassBody,
    me: dict = Depends(require_instructor),
    db: sqlite3.Connection = Depends(get_db),
):
    cls = repo.create_class(
        db, me["instructor_id"], name=body.name, term=body.term, timezone=body.timezone
    )
    return _class_out(cls)


@router.get("/classes")
def list_classes(
    me: dict = Depends(require_instructor), db: sqlite3.Connection = Depends(get_db)
):
    return [_class_out(c) for c in repo.list_classes(db, me["instructor_id"])]


@router.get("/classes/{class_id}")
def get_class(cls: dict = Depends(require_owned_class)):
    return _class_out(cls)


@router.put("/classes/{class_id}/roster")
def replace_roster(
    body: RosterBody,
    cls: dict = Depends(require_owned_class),
    db: sqlite3.Connection = Depends(get_db),
):
    try:
        repo.replace_roster(db, cls["id"], [(s.student_id, s.name) for s in body.students])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"count": len(body.students)}


@router.get("/classes/{class_id}/roster")
def get_roster(
    cls: dict = Depends(require_owned_class), db: sqlite3.Connection = Depends(get_db)
):
    students = [
        {
            "student_id": r["student_ext_id"],
            "name": r["name"],
            "joined": r["enrollment_id"] is not None,
        }
        for r in repo.list_roster(db, cls["id"])
    ]
    return {"students": students}
