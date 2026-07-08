"""Instructor cycle routes: create/list cycles, config, roster-status."""

import sqlite3
import statistics
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
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
from reflectool.output_format import build_proposal
from reflectool.review_workflow import (
    IllegalTransition,
    InvalidEdit,
    Session,
    apply_edit,
    approve as workflow_approve,
    composition_view,
    publish as workflow_publish,
)

from .. import repo, sessions
from ..auth import get_db, require_instructor, require_owned_class

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
