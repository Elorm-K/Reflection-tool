"""Instructor cycle routes: create/list cycles, config, roster-status."""

import sqlite3
import statistics
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from reflectool.io_parse import ValidationError, parse_config

from .. import repo, sessions
from ..auth import get_db, require_instructor, require_owned_class

router = APIRouter(prefix="/api")


class CycleBody(BaseModel):
    label: str = ""
    deadline: str | None = None
    config: dict = {}


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
