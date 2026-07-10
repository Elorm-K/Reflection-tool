"""Student-facing routes. Every response body passes student_safe()."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from reflectool.io_parse import ValidationError, parse_config, parse_roster
from reflectool.notify import PreApprovalLeak, student_view

from .. import repo, sessions
from ..auth import get_db, require_student
from ..privacy import student_safe

router = APIRouter(prefix="/api")


class JoinBody(BaseModel):
    class_code: str = Field(min_length=1)
    student_id: str = Field(min_length=1)


class AvailabilityBody(BaseModel):
    slots: list[bool | int]


class SurveyBody(BaseModel):
    gender: str | None = None
    disability: str | None = None
    skip: bool = False


class MessageBody(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class MeetingBody(BaseModel):
    label: str


def _clean_meeting_label(label: str) -> str:
    cleaned = label.strip()
    if not cleaned or len(cleaned) > 120:
        raise HTTPException(
            status_code=422,
            detail="meeting time must be 1-120 characters",
        )
    return cleaned


def _meeting_out(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {"label": row["label"], "set_by": row["set_by"],
            "updated_at": row["updated_at"]}


def _current_cycle(db: sqlite3.Connection, ctx: dict) -> dict:
    cycle = repo.current_cycle_for_class(db, ctx["class_id"])
    if cycle is None:
        raise HTTPException(status_code=404, detail="no active cycle for this class")
    return cycle


def _require_collecting(cycle: dict) -> None:
    if cycle["status"] != "collecting":
        raise HTTPException(
            status_code=409,
            detail="submissions are closed for this cycle",
        )


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
                "grid": sessions.grid_out(cycle["config"]),
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


@router.put("/me/availability")
def submit_availability(
    body: AvailabilityBody,
    ctx: dict = Depends(require_student),
    db: sqlite3.Connection = Depends(get_db),
):
    cycle = _current_cycle(db, ctx)
    _require_collecting(cycle)
    config = parse_config(cycle["config"])
    try:
        parse_roster(
            [{"id": ctx["student_ext_id"], "availability": list(body.slots)}], config
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    repo.upsert_availability(db, cycle["id"], ctx["enrollment_id"], list(body.slots))
    repo.add_audit(db, cycle["id"], actor=ctx["student_ext_id"],
                   action="availability-submitted")
    return student_safe({"ok": True, "slots_selected": sum(bool(v) for v in body.slots)})


@router.put("/me/survey")
def submit_survey(
    body: SurveyBody,
    ctx: dict = Depends(require_student),
    db: sqlite3.Connection = Depends(get_db),
):
    cycle = _current_cycle(db, ctx)
    _require_collecting(cycle)
    if body.skip:
        repo.upsert_survey(db, cycle["id"], ctx["enrollment_id"], skipped=True)
    else:
        repo.upsert_survey(
            db, cycle["id"], ctx["enrollment_id"],
            gender=body.gender, disability=body.disability,
        )
    repo.add_audit(db, cycle["id"], actor=ctx["student_ext_id"], action="survey-submitted")
    # Survey values are stored, never echoed back — not even to the submitter.
    return student_safe({"ok": True})


@router.get("/me/group")
def my_group(
    ctx: dict = Depends(require_student), db: sqlite3.Connection = Depends(get_db)
):
    cycle = _current_cycle(db, ctx)
    if not cycle["session_json"] or cycle["status"] != "published":
        # One generic message for every pre-publication state: a student must
        # not be able to distinguish proposed from approved.
        raise HTTPException(status_code=409, detail="your group is not published yet")
    session, _ = sessions.load_session(cycle)
    try:
        view = student_view(session, ctx["student_ext_id"])
    except PreApprovalLeak:
        raise HTTPException(status_code=409, detail="your group is not published yet")
    except KeyError:
        raise HTTPException(status_code=404, detail="you are not part of this cycle")
    if "group_number" in view:
        view["chosen_meeting"] = _meeting_out(
            repo.get_group_meeting(db, cycle["id"], view["group_number"])
        )
    return student_safe(view)


@router.get("/me/notifications")
def my_notifications(
    ctx: dict = Depends(require_student), db: sqlite3.Connection = Depends(get_db)
):
    """In-app notices (e.g. post-publish reassignment). Bodies were built
    demographic-free at write time; asserted again here anyway."""
    notes = [
        {"id": n["id"], "kind": n["kind"], "body": n["body"],
         "created_at": n["created_at"], "read_at": n["read_at"]}
        for n in repo.list_notifications(db, ctx["enrollment_id"])
    ]
    unread = repo.count_unread_notifications(db, ctx["enrollment_id"])
    return student_safe({"notifications": notes, "unread": unread})


@router.post("/me/notifications/read")
def mark_my_notifications_read(
    ctx: dict = Depends(require_student), db: sqlite3.Connection = Depends(get_db)
):
    marked = repo.mark_notifications_read(db, ctx["enrollment_id"])
    return student_safe({"ok": True, "marked": marked})


def _published_group(db: sqlite3.Connection, ctx: dict) -> tuple[dict, dict]:
    """The student's group in the published proposal, or 409/404."""
    cycle = _current_cycle(db, ctx)
    if not cycle["session_json"] or cycle["status"] != "published":
        raise HTTPException(status_code=409, detail="your group is not published yet")
    session, _ = sessions.load_session(cycle)
    for group in session.proposal["groups"]:
        if ctx["student_ext_id"] in group["members"]:
            return cycle, group
    raise HTTPException(status_code=404, detail="you are not in a group this cycle")


@router.put("/me/group/meeting")
def set_group_meeting(
    body: MeetingBody,
    ctx: dict = Depends(require_student),
    db: sqlite3.Connection = Depends(get_db),
):
    """A group member records the meeting time the group agreed on. Overlay
    only — the matcher's proposal is never touched. Other members get an
    in-app notification."""
    label = _clean_meeting_label(body.label)
    cycle, group = _published_group(db, ctx)
    setter = ctx["name"] or ctx["student_ext_id"]
    row = repo.set_group_meeting(db, cycle["id"], group["group_id"], label, set_by=setter)
    note = f'{setter} set your group\'s meeting time to "{label}".'
    student_safe({"body": note})
    for sid in group["members"]:
        if sid == ctx["student_ext_id"]:
            continue
        enrollment = repo.get_enrollment_for_student(db, ctx["class_id"], sid)
        if enrollment is not None:
            repo.add_notification(db, cycle["id"], enrollment["id"],
                                  kind="meeting-updated", body=note)
    return student_safe({"ok": True, "chosen_meeting": _meeting_out(row)})


def _message_out(m: dict) -> dict:
    return {
        "id": m["id"],
        "sender_id": m["sender_id"],
        "sender_name": m["sender_name"],
        "body": m["body"],
        "created_at": m["created_at"],
    }


@router.get("/me/group/messages")
def list_group_messages(
    since: int = 0,
    ctx: dict = Depends(require_student),
    db: sqlite3.Connection = Depends(get_db),
):
    cycle, group = _published_group(db, ctx)
    messages = [_message_out(m) for m in
                repo.list_messages(db, cycle["id"], group["group_id"], since=since)]
    return student_safe({"messages": messages})


@router.post("/me/group/messages", status_code=201)
def post_group_message(
    body: MessageBody,
    ctx: dict = Depends(require_student),
    db: sqlite3.Connection = Depends(get_db),
):
    cycle, group = _published_group(db, ctx)
    message = repo.add_message(db, cycle["id"], group["group_id"], ctx["enrollment_id"],
                               body.body)
    return student_safe(
        _message_out({**message, "sender_id": ctx["student_ext_id"],
                      "sender_name": ctx["name"]})
    )
