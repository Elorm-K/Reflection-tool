"""Student-facing routes. Every response body passes student_safe()."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import repo
from ..auth import get_db, require_student
from ..privacy import student_safe

router = APIRouter(prefix="/api")


class JoinBody(BaseModel):
    class_code: str = Field(min_length=1)
    student_id: str = Field(min_length=1)


@router.post("/join")
def join(body: JoinBody, db: sqlite3.Connection = Depends(get_db)):
    cls = repo.get_class_by_code(db, body.class_code)
    if cls is None:
        raise HTTPException(status_code=404, detail="unknown class code")
    enrollment = repo.claim_enrollment(db, cls["id"], body.student_id)
    if enrollment is None:
        raise HTTPException(status_code=404, detail="student id not on the class roster")
    ctx = repo.get_enrollment_context(db, enrollment["id"])
    token = repo.issue_token(db, kind="student", enrollment_id=enrollment["id"])
    return student_safe(
        {
            "token": token,
            "student_id": ctx["student_ext_id"],
            "name": ctx["name"],
            "class_name": cls["name"],
        }
    )


@router.get("/me")
def me(ctx: dict = Depends(require_student), db: sqlite3.Connection = Depends(get_db)):
    cycle = repo.current_cycle_for_class(db, ctx["class_id"])
    submission = (
        repo.get_submission(db, cycle["id"], ctx["enrollment_id"]) if cycle else None
    )
    return student_safe(
        {
            "student_id": ctx["student_ext_id"],
            "name": ctx["name"],
            "cycle": None
            if cycle is None
            else {
                "label": cycle["label"],
                "deadline": cycle["deadline"],
                "phase": cycle["status"],
            },
            "availability_submitted": bool(submission and submission["availability"]),
            "survey_submitted": bool(
                submission
                and (
                    submission["survey_skipped"]
                    or submission["gender"] is not None
                    or submission["disability"] is not None
                )
            ),
        }
    )
