"""Human-in-the-loop review gate (spec section 4.6).

Manages the proposed -> approved -> published state machine, the
instructor-only composition view (the one authorized place identity is
visible), and manual edits, each re-validated against the hard constraints
before it can be saved. The matcher core knows nothing about this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .io_parse import Config, Student
from .objective import group_overlap_slots, homogeneity
from .output_format import assert_no_demographics

TRANSITIONS = {"proposed": "approved", "approved": "published"}


class WorkflowError(Exception):
    pass


class IllegalTransition(WorkflowError):
    pass


class InvalidEdit(WorkflowError):
    pass


@dataclass
class Session:
    roster: list[Student]
    config: Config
    proposal: dict
    audit_log: list[str] = field(default_factory=list)

    def student(self, student_id: str) -> Student:
        for s in self.roster:
            if s.student_id == student_id:
                return s
        raise KeyError(f"unknown student id: {student_id}")

    def group_members(self, group_id: int) -> list[Student]:
        for g in self.proposal["groups"]:
            if g["group_id"] == group_id:
                return [self.student(sid) for sid in g["members"]]
        raise InvalidEdit(f"no group with id {group_id}")


def _transition(session: Session, target: str) -> None:
    current = session.proposal["status"]
    if TRANSITIONS.get(current) != target:
        raise IllegalTransition(
            f"cannot go from {current!r} to {target!r}; "
            f"the only legal path is proposed -> approved -> published"
        )
    assert_no_demographics(session.proposal)
    session.proposal["status"] = target
    session.audit_log.append(f"status -> {target}")


def approve(session: Session) -> None:
    _transition(session, "approved")


def publish(session: Session) -> None:
    _transition(session, "published")


def composition_view(session: Session) -> dict:
    """Instructor-only: per-group aggregate composition and homogeneity.

    This never leaves the review context and is never persisted into the
    proposal or shown to students (spec 4.6 step 3).
    """
    groups = []
    for g in session.proposal["groups"]:
        members = [session.student(sid) for sid in g["members"]]
        gender_comp: dict[str, int] = {}
        disability_comp: dict[str, int] = {}
        for s in members:
            gender_comp[s.gender] = gender_comp.get(s.gender, 0) + 1
            disability_comp[s.disability] = disability_comp.get(s.disability, 0) + 1
        groups.append(
            {
                "group_id": g["group_id"],
                "size": len(members),
                "meeting_slots": g["meeting_slots"],
                "gender_composition": gender_comp,
                "disability_composition": disability_comp,
                "gender_homogeneity": homogeneity(members, "gender"),
                "disability_homogeneity": homogeneity(members, "disability"),
            }
        )
    return {"groups": groups, "unplaced": session.proposal["unplaced"], "warnings": session.proposal["warnings"]}


def _validate_group(session: Session, members: list[Student], allow_oversize: bool) -> None:
    config = session.config
    max_size = config.max_size + 1 if allow_oversize else config.max_size
    if not (config.min_size <= len(members) <= max_size):
        raise InvalidEdit(
            f"group size {len(members)} violates size bounds "
            f"[{config.min_size}, {config.max_size}]"
            + ("" if allow_oversize else " (pass allow_oversize for an explicit instructor override)")
        )
    if len(group_overlap_slots(members)) < config.min_overlap:
        raise InvalidEdit(
            f"group would share fewer than min_overlap={config.min_overlap} mutually free slots"
        )


def _refresh_group(session: Session, group: dict) -> None:
    members = [session.student(sid) for sid in group["members"]]
    shared = group_overlap_slots(members)
    group["meeting_slots"] = [
        session.config.grid.slot_label(i) for i in shared[: session.config.min_overlap]
    ]


def apply_edit(session: Session, edit: dict) -> None:
    """Apply a manual instructor edit (move / assign an unplaced student),
    re-validating hard constraints; invalid edits leave the session unchanged."""
    if session.proposal["status"] != "proposed":
        raise IllegalTransition(
            f"edits are only allowed while status is 'proposed', not {session.proposal['status']!r}"
        )
    action = edit.get("action")
    student_id = edit.get("student_id")
    to_group = edit.get("to_group")
    allow_oversize = bool(edit.get("allow_oversize"))
    student = session.student(student_id)
    groups = session.proposal["groups"]
    target = next((g for g in groups if g["group_id"] == to_group), None)
    if target is None:
        raise InvalidEdit(f"no group with id {to_group}")

    if action == "move":
        source = next((g for g in groups if student_id in g["members"]), None)
        if source is None:
            raise InvalidEdit(f"{student_id} is not in any group (use action 'assign')")
        if source["group_id"] == to_group:
            raise InvalidEdit(f"{student_id} is already in group {to_group}")
        new_source = [session.student(sid) for sid in source["members"] if sid != student_id]
        new_target = [session.student(sid) for sid in target["members"]] + [student]
        _validate_group(session, new_source, allow_oversize=False)
        _validate_group(session, new_target, allow_oversize)
        source["members"] = [sid for sid in source["members"] if sid != student_id]
        target["members"] = sorted(target["members"] + [student_id])
        _refresh_group(session, source)
        _refresh_group(session, target)
        session.audit_log.append(
            f"move {student_id}: group {source['group_id']} -> {to_group}"
            + (" [oversize override]" if allow_oversize and len(target["members"]) > session.config.max_size else "")
        )
    elif action == "assign":
        if not any(u["student_id"] == student_id for u in session.proposal["unplaced"]):
            raise InvalidEdit(f"{student_id} is not on the unplaced list")
        new_target = [session.student(sid) for sid in target["members"]] + [student]
        _validate_group(session, new_target, allow_oversize)
        target["members"] = sorted(target["members"] + [student_id])
        session.proposal["unplaced"] = [
            u for u in session.proposal["unplaced"] if u["student_id"] != student_id
        ]
        _refresh_group(session, target)
        session.audit_log.append(f"assign unplaced {student_id} -> group {to_group}")
    else:
        raise InvalidEdit(f"unknown edit action: {action!r}")
    assert_no_demographics(session.proposal)
