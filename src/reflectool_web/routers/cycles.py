"""Instructor cycle routes: create/list cycles, config, roster-status."""

import csv
import io
import sqlite3
import statistics
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from typing import Literal

from reflectool.io_parse import (
    ValidationError,
    normalize_disability,
    normalize_gender,
    parse_config,
    parse_roster,
)
from reflectool.matcher import match as run_match
from reflectool.notify import all_notifications
from reflectool.objective import group_overlap_slots
from reflectool.output_format import assert_no_demographics
from reflectool.output_format import build_proposal
from reflectool.review_workflow import (
    IllegalTransition,
    InvalidEdit,
    Session,
    apply_edit,
    apply_live_edit,
    approve as workflow_approve,
    composition_view,
    publish as workflow_publish,
)

from .. import repo, sessions
from ..auth import get_db, require_instructor, require_owned_class
from ..privacy import student_safe

router = APIRouter(prefix="/api")


class CycleBody(BaseModel):
    label: str = ""
    deadline: str | None = None
    config: dict = {}


class EditBody(BaseModel):
    action: Literal["move", "assign"]
    student_id: str
    to_group: int
    allow_oversize: bool = False


class ReassignmentBody(BaseModel):
    action: Literal["move", "assign"]
    student_id: str
    to_group: int
    allow_oversize: bool = False
    # Server-enforced: groups are live, so the instructor must confirm
    # explicitly — a UI dialog alone would be bypassable by any API client.
    confirm: bool = False


def _session_or_404(cycle: dict) -> tuple[Session, list[dict]]:
    if not cycle["session_json"]:
        raise HTTPException(status_code=404, detail="no proposal yet — run match first")
    return sessions.load_session(cycle)


def _stamp_reviewed(db: sqlite3.Connection, cycle: dict) -> None:
    repo.update_cycle(db, cycle["id"], reviewed_rev=cycle["proposal_rev"])


def _now(db: sqlite3.Connection) -> str:
    return db.execute("SELECT datetime('now')").fetchone()[0]


def require_owned_cycle(
    cycle_id: int,
    me: dict = Depends(require_instructor),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    cycle = repo.get_cycle(db, cycle_id)
    if cycle is not None:
        cls = repo.get_class(db, cycle["class_id"])
        if cls is not None and cls["instructor_id"] == me["instructor_id"]:
            return cycle
    raise HTTPException(status_code=404, detail="cycle not found")


def cycle_out(cycle: dict) -> dict:
    return {
        "id": cycle["id"],
        "class_id": cycle["class_id"],
        "label": cycle["label"],
        "deadline": cycle["deadline"],
        "status": cycle["status"],
        "proposal_rev": cycle["proposal_rev"],
        "reviewed_rev": cycle["reviewed_rev"],
        "config": sessions.config_out(cycle["config"]),
        "created_at": cycle["created_at"],
    }


@router.post("/classes/{class_id}/cycles", status_code=201)
def create_cycle(
    body: CycleBody,
    cls: dict = Depends(require_owned_class),
    db: sqlite3.Connection = Depends(get_db),
):
    try:
        config = sessions.normalize_config(body.config)
    except (ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid config: {exc}")
    cycle = repo.create_cycle(db, cls["id"], label=body.label, config=config,
                              deadline=body.deadline)
    repo.add_audit(db, cycle["id"], actor="instructor", action="cycle-created",
                   detail=body.label)
    return cycle_out(cycle)


@router.get("/classes/{class_id}/cycles")
def list_cycles(
    cls: dict = Depends(require_owned_class), db: sqlite3.Connection = Depends(get_db)
):
    return [cycle_out(c) for c in repo.list_cycles(db, cls["id"])]


@router.get("/cycles/{cycle_id}")
def get_cycle(cycle: dict = Depends(require_owned_cycle)):
    return cycle_out(cycle)


@router.patch("/cycles/{cycle_id}/config")
def patch_config(
    body: dict,
    cycle: dict = Depends(require_owned_cycle),
    db: sqlite3.Connection = Depends(get_db),
):
    if cycle["status"] != "collecting":
        raise HTTPException(
            status_code=409,
            detail=f"config is frozen once matching has run (status: {cycle['status']});"
            " start a new cycle instead",
        )
    merged = {**cycle["config"], **body}
    if "grid" in body and repo.count_submissions(db, cycle["id"]) > 0:
        if sessions.normalize_config(merged)["grid"] != cycle["config"]["grid"]:
            raise HTTPException(
                status_code=409,
                detail="the availability grid is locked once the first submission exists",
            )
    try:
        config = sessions.normalize_config(merged)
    except (ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid config: {exc}")
    repo.update_cycle(db, cycle["id"], config=config)
    repo.add_audit(db, cycle["id"], actor="instructor", action="config-updated")
    return cycle_out(repo.get_cycle(db, cycle["id"]))


@router.post("/cycles/{cycle_id}/match")
def match_cycle(
    cycle: dict = Depends(require_owned_cycle), db: sqlite3.Connection = Depends(get_db)
):
    """Run the deterministic matcher over stored submissions.

    Allowed while collecting (first match) or proposed (re-match / RESET);
    blocked once approved — the instructor must start a new cycle instead.
    """
    if cycle["status"] not in ("collecting", "proposed"):
        raise HTTPException(
            status_code=409,
            detail=f"cannot re-match a cycle in status '{cycle['status']}'",
        )
    raw_students = sessions.assemble_raw_students(db, cycle["id"])
    if not raw_students:
        raise HTTPException(status_code=409, detail="no availability submissions yet")
    config = parse_config(cycle["config"])
    students = parse_roster(raw_students, config)
    proposal = build_proposal(run_match(students, config), config)
    session = Session(
        roster=students, config=config, proposal=proposal,
        audit_log=["match: proposal generated"],
    )
    sessions.save_session(db, cycle["id"], session, raw_students)
    repo.update_cycle(db, cycle["id"], proposal_rev=cycle["proposal_rev"] + 1)
    repo.add_audit(
        db, cycle["id"], actor="instructor", action="match",
        detail=f"groups={len(proposal['groups'])} unplaced={len(proposal['unplaced'])}",
    )
    return proposal


@router.get("/cycles/{cycle_id}/proposal")
def get_proposal(cycle: dict = Depends(require_owned_cycle)):
    if not cycle["session_json"]:
        raise HTTPException(status_code=404, detail="no proposal yet — run match first")
    session, _ = sessions.load_session(cycle)
    return session.proposal


@router.get("/cycles/{cycle_id}/review-board")
def review_board(
    cycle: dict = Depends(require_owned_cycle), db: sqlite3.Connection = Depends(get_db)
):
    """Live instructor review surface. The ONLY endpoint that serves
    per-student demographics; rendered from raw_students at request time,
    never persisted into the proposal."""
    session, raw_students = _session_or_404(cycle)
    students = {
        raw["id"]: {
            "name": raw.get("name", ""),
            "gender": normalize_gender(raw.get("gender")),
            "disability": normalize_disability(raw.get("disability")),
            "availability": [bool(v) for v in raw["availability"]],
            "free_slot_count": sum(1 for v in raw["availability"] if v),
        }
        for raw in raw_students
    }
    _stamp_reviewed(db, cycle)
    repo.add_audit(db, cycle["id"], actor="instructor", action="review-board-viewed",
                   detail=f"rev={cycle['proposal_rev']}")
    return {
        "proposal": session.proposal,
        "students": students,
        "config": sessions.config_out(cycle["config"]),
    }


@router.get("/cycles/{cycle_id}/composition")
def composition(
    cycle: dict = Depends(require_owned_cycle), db: sqlite3.Connection = Depends(get_db)
):
    """Per-group demographic aggregates (instructor-only)."""
    session, _ = _session_or_404(cycle)
    view = composition_view(session)
    _stamp_reviewed(db, cycle)
    repo.add_audit(db, cycle["id"], actor="instructor", action="composition-viewed",
                   detail=f"rev={cycle['proposal_rev']}")
    return view


@router.post("/cycles/{cycle_id}/edits")
def edit_proposal(
    body: EditBody,
    cycle: dict = Depends(require_owned_cycle),
    db: sqlite3.Connection = Depends(get_db),
):
    session, raw_students = _session_or_404(cycle)
    try:
        apply_edit(session, body.model_dump())
    except InvalidEdit as exc:
        # Relay the exact violated constraint; never force the edit through.
        raise HTTPException(status_code=422, detail=str(exc))
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown student: {body.student_id}")
    sessions.save_session(db, cycle["id"], session, raw_students)
    repo.update_cycle(db, cycle["id"], proposal_rev=cycle["proposal_rev"] + 1)
    repo.add_audit(db, cycle["id"], actor="instructor", action="edit",
                   detail=f"{body.action} {body.student_id} -> group {body.to_group}")
    return session.proposal


def _notify_reassignment(db: sqlite3.Connection, cycle: dict, session: Session,
                         summary: dict) -> int:
    """Record in-app notifications (and inactive email records) for everyone a
    live reassignment touches: the moved/assigned student plus all current
    members of the source and target groups — a move can change a group's
    meeting time, and silent changes are never acceptable (invariant 4).

    Bodies are built exclusively from proposal data (group ids, meeting slots)
    and pass student_safe() before they are written anywhere."""
    student_id = summary["student_id"]
    groups = {g["group_id"]: g for g in session.proposal["groups"]}
    target = groups[summary["to_group"]]
    slots = ", ".join(target["meeting_slots"])
    if summary["action"] == "move":
        moved_body = (f"Your instructor moved you to Group {target['group_id']}."
                      f" New meeting time: {slots}.")
    else:
        moved_body = (f"You have been assigned to Group {target['group_id']}."
                      f" Meeting time: {slots}.")
    member_body = ("Your group's membership was updated by your instructor."
                   " Check My Group for the current members and meeting time.")

    affected = {student_id: ("group-changed", moved_body)}
    member_ids = set(target["members"])
    if summary["from_group"] is not None:
        member_ids |= set(groups[summary["from_group"]]["members"])
    for sid in member_ids - {student_id}:
        affected[sid] = ("group-updated", member_body)

    notified = 0
    for sid, (kind, body) in affected.items():
        student_safe({"body": body})
        enrollment = repo.get_enrollment_for_student(db, cycle["class_id"], sid)
        if enrollment is None:
            continue  # on the proposal but never claimed a seat — nothing to notify
        repo.add_notification(db, cycle["id"], enrollment["id"], kind=kind, body=body)
        repo.add_outbox_email(db, kind=kind, subject="Your discussion group changed",
                              body=body, enrollment_id=enrollment["id"])
        notified += 1
    return notified


@router.post("/cycles/{cycle_id}/reassignments")
def reassign_student(
    body: ReassignmentBody,
    cycle: dict = Depends(require_owned_cycle),
    db: sqlite3.Connection = Depends(get_db),
):
    """Move/assign a student on a *published* cycle. Requires confirm=true,
    re-validates the hard constraints, and notifies every affected student.
    Does not touch proposal_rev/reviewed_rev — the approve gate is behind us."""
    if not body.confirm:
        raise HTTPException(
            status_code=422,
            detail="explicit confirmation required — this cycle is published and"
            " groups are live; resend with confirm=true",
        )
    session, raw_students = _session_or_404(cycle)
    edit = body.model_dump(exclude={"confirm"})
    try:
        summary = apply_live_edit(session, edit)
    except InvalidEdit as exc:
        # Relay the exact violated constraint; never force the edit through.
        raise HTTPException(status_code=422, detail=str(exc))
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown student: {body.student_id}")
    sessions.save_session(db, cycle["id"], session, raw_students)
    notified = _notify_reassignment(db, cycle, session, summary)
    repo.add_audit(db, cycle["id"], actor="instructor", action="reassign",
                   detail=f"{body.action} {body.student_id} -> group {body.to_group}"
                          f" notified={notified}")
    return {"proposal": session.proposal, "notified": notified}


@router.post("/cycles/{cycle_id}/approve")
def approve_cycle(
    cycle: dict = Depends(require_owned_cycle), db: sqlite3.Connection = Depends(get_db)
):
    """Approval gate: the instructor must have viewed the current revision of
    the proposal (review board or composition) since the last match/edit."""
    session, raw_students = _session_or_404(cycle)
    if cycle["reviewed_rev"] != cycle["proposal_rev"]:
        raise HTTPException(
            status_code=409,
            detail="review required: view the current proposal (review board or"
            " composition) before approving — it changed since your last look",
        )
    try:
        workflow_approve(session)
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    sessions.save_session(db, cycle["id"], session, raw_students)
    repo.update_cycle(db, cycle["id"], approved_at=_now(db))
    repo.add_audit(db, cycle["id"], actor="instructor", action="approve")
    return {"status": session.proposal["status"]}


@router.post("/cycles/{cycle_id}/publish")
def publish_cycle(
    cycle: dict = Depends(require_owned_cycle), db: sqlite3.Connection = Depends(get_db)
):
    session, raw_students = _session_or_404(cycle)
    try:
        workflow_publish(session)
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    sessions.save_session(db, cycle["id"], session, raw_students)
    repo.update_cycle(db, cycle["id"], published_at=_now(db))
    notified = len(all_notifications(session))
    repo.add_audit(db, cycle["id"], actor="instructor", action="publish",
                   detail=f"notified={notified}")
    return {"status": session.proposal["status"], "notified": notified}


@router.get("/cycles/{cycle_id}/notifications")
def notifications_preview(
    cycle: dict = Depends(require_owned_cycle), db: sqlite3.Connection = Depends(get_db)
):
    """Instructor preview of every student's notification (already
    student-safe payloads)."""
    session, _ = _session_or_404(cycle)
    try:
        return all_notifications(session)
    except Exception as exc:  # PreApprovalLeak before publish
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/cycles/{cycle_id}/groups/{group_id}/messages")
def group_messages(
    group_id: int,
    since: int = 0,
    cycle: dict = Depends(require_owned_cycle),
    db: sqlite3.Connection = Depends(get_db),
):
    """Instructor read access to a group's chat (disclosed to students in the
    chat UI)."""
    messages = [
        {"id": m["id"], "sender_id": m["sender_id"], "sender_name": m["sender_name"],
         "body": m["body"], "created_at": m["created_at"]}
        for m in repo.list_messages(db, cycle["id"], group_id, since=since)
    ]
    return {"messages": messages}


@router.get("/cycles/{cycle_id}/export.csv")
def export_csv(cycle: dict = Depends(require_owned_cycle)):
    """Groups as CSV, built from the proposal only — demographic-free by
    construction, and asserted anyway."""
    session, _ = _session_or_404(cycle)
    rows = []
    names = {s.student_id: s.name for s in session.roster}
    for group in session.proposal["groups"]:
        for sid in group["members"]:
            rows.append({
                "group_id": group["group_id"],
                "student_id": sid,
                "name": names.get(sid, ""),
                "meeting_slots": " ".join(group["meeting_slots"]),
            })
    assert_no_demographics(rows)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["group_id", "student_id", "name",
                                             "meeting_slots"])
    writer.writeheader()
    writer.writerows(rows)
    return PlainTextResponse(buf.getvalue(), media_type="text/csv")


@router.get("/cycles/{cycle_id}/explain/{student_id}")
def explain(student_id: str, cycle: dict = Depends(require_owned_cycle)):
    """Privacy-safe placement facts: schedule and config only."""
    session, _ = _session_or_404(cycle)
    try:
        session.student(student_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown student: {student_id}")
    for g in session.proposal["groups"]:
        if student_id in g["members"]:
            members = [session.student(sid) for sid in g["members"]]
            return {
                "student_id": student_id,
                "group_id": g["group_id"],
                "group_size": len(members),
                "shared_slot_count": len(group_overlap_slots(members)),
                "meeting_slots": g["meeting_slots"],
                "min_overlap_required": session.config.min_overlap,
                "status": session.proposal["status"],
            }
    reason = next(
        (u["reason"] for u in session.proposal["unplaced"]
         if u["student_id"] == student_id),
        None,
    )
    return {"student_id": student_id, "unplaced": True, "reason": reason}


@router.get("/cycles/{cycle_id}/audit")
def audit_trail(
    cycle: dict = Depends(require_owned_cycle), db: sqlite3.Connection = Depends(get_db)
):
    return {"entries": repo.list_audit(db, cycle["id"])}


class ResetClaimBody(BaseModel):
    student_id: str


@router.post("/classes/{class_id}/reset-claim")
def reset_claim(
    body: ResetClaimBody,
    cls: dict = Depends(require_owned_class),
    db: sqlite3.Connection = Depends(get_db),
):
    """Clear a student's enrollment (and their tokens/submissions/messages) so
    the right person can re-claim the seat."""
    if not repo.reset_claim(db, cls["id"], body.student_id):
        raise HTTPException(status_code=404, detail="no claim to reset for that student")
    return {"ok": True}


@router.get("/cycles/{cycle_id}/roster-status")
def roster_status(
    cycle: dict = Depends(require_owned_cycle), db: sqlite3.Connection = Depends(get_db)
):
    """Intake aggregates (cmd_intake logic). Instructor-only: contains
    demographic counts."""
    config = parse_config(cycle["config"])
    roster = repo.list_roster(db, cycle["class_id"])
    subs = [s for s in repo.list_submissions(db, cycle["id"]) if s["availability"]]
    submitted_ids = {s["student_ext_id"] for s in subs}

    free_counts = [sum(1 for v in s["availability"] if v) for s in subs]
    gender_counts = Counter()
    disability_counts = Counter()
    for s in subs:
        if s["gender"]:
            gender_counts[s["gender"]] += 1
        if s["disability"]:
            disability_counts[s["disability"]] += 1

    return {
        "roster_count": len(roster),
        "joined_count": sum(1 for r in roster if r["enrollment_id"] is not None),
        "submitted_count": len(subs),
        "missing": [r["student_ext_id"] for r in roster
                    if r["student_ext_id"] not in submitted_ids],
        "gender_counts": dict(gender_counts),
        "disability_counts": dict(disability_counts),
        "min_free_slots": min(free_counts) if free_counts else 0,
        "median_free_slots": statistics.median(free_counts) if free_counts else 0,
        "students_below_min_overlap": sum(
            1 for c in free_counts if c < config.min_overlap
        ),
    }
