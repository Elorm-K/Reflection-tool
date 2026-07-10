"""Skill-facing CLI. Every Claude Skill action maps to one subcommand here,
so groupings come from the deterministic matcher, never from the model.

State (roster + config + proposal + audit log) persists to a JSON session
file between invocations. The session file lives server-side with the
instructor's own collected data; everything printed by student-facing
subcommands passes the no-demographics guard.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .io_parse import Config, Grid, ValidationError, parse_config, parse_roster
from .matcher import match
from .notify import all_notifications, student_view
from .objective import group_overlap_slots
from .output_format import build_proposal
from .review_workflow import Session, WorkflowError, apply_edit, approve, composition_view, publish


def _load_roster_file(path: str) -> tuple[list, dict]:
    data = json.loads(Path(path).read_text())
    return data["students"], data.get("config") or {}


def _config_to_dict(config: Config) -> dict:
    return {
        "target_size": config.target_size,
        "min_size": config.min_size,
        "max_size": config.max_size,
        "min_overlap": config.min_overlap,
        "priority": list(config.priority),
        "tiebreak_seed": config.tiebreak_seed,
        "grid": {
            "days": config.grid.days,
            "start": config.grid.start,
            "end": config.grid.end,
            "slot_minutes": config.grid.slot_minutes,
        },
    }


def _save_session(state_path: str, session: Session, raw_students: list) -> None:
    Path(state_path).parent.mkdir(parents=True, exist_ok=True)
    Path(state_path).write_text(
        json.dumps(
            {
                "raw_students": raw_students,
                "config": _config_to_dict(session.config),
                "proposal": session.proposal,
                "audit_log": session.audit_log,
            },
            indent=2,
        )
    )


def _load_session(state_path: str) -> tuple[Session, list]:
    data = json.loads(Path(state_path).read_text())
    config = parse_config(data["config"])
    roster = parse_roster(data["raw_students"], config)
    session = Session(
        roster=roster,
        config=config,
        proposal=data["proposal"],
        audit_log=data["audit_log"],
    )
    return session, data["raw_students"]


def _emit(obj) -> None:
    print(json.dumps(obj, indent=2))


def cmd_intake(args) -> int:
    raw_students, raw_config = _load_roster_file(args.roster)
    config = parse_config(raw_config)
    students = parse_roster(raw_students, config)
    free_counts = [sum(s.availability) for s in students]
    _emit(
        {
            "students": len(students),
            "grid_slots": config.grid.num_slots,
            "gender_counts": dict(Counter(s.gender for s in students)),
            "disability_counts": dict(Counter(s.disability for s in students)),
            "min_free_slots": min(free_counts),
            "median_free_slots": sorted(free_counts)[len(free_counts) // 2],
            "students_below_min_overlap": sum(
                1 for c in free_counts if c < config.min_overlap
            ),
        }
    )
    return 0


def cmd_match(args) -> int:
    raw_students, raw_config = _load_roster_file(args.roster)
    if args.min_overlap is not None:
        raw_config["min_overlap"] = args.min_overlap
    if args.priority:
        raw_config["priority"] = args.priority.split(",")
    config = parse_config(raw_config)
    students = parse_roster(raw_students, config)
    proposal = build_proposal(match(students, config), config)
    session = Session(roster=students, config=config, proposal=proposal)
    session.audit_log.append("match: proposal generated")
    _save_session(args.state, session, raw_students)
    _emit(proposal)
    return 0


def cmd_show(args) -> int:
    session, _ = _load_session(args.state)
    _emit(session.proposal)
    return 0


def cmd_composition(args) -> int:
    session, _ = _load_session(args.state)
    _emit(composition_view(session))
    return 0


def cmd_edit(args) -> int:
    session, raw_students = _load_session(args.state)
    apply_edit(
        session,
        {
            "action": args.action,
            "student_id": args.student,
            "to_group": args.to_group,
            "allow_oversize": args.allow_oversize,
            "allow_low_overlap": args.allow_low_overlap,
        },
    )
    _save_session(args.state, session, raw_students)
    _emit(session.proposal)
    return 0


def cmd_approve(args) -> int:
    session, raw_students = _load_session(args.state)
    approve(session)
    _save_session(args.state, session, raw_students)
    _emit({"status": session.proposal["status"]})
    return 0


def cmd_publish(args) -> int:
    session, raw_students = _load_session(args.state)
    publish(session)
    _save_session(args.state, session, raw_students)
    _emit({"status": session.proposal["status"], "notified": len(all_notifications(session))})
    return 0


def cmd_student_view(args) -> int:
    session, _ = _load_session(args.state)
    _emit(student_view(session, args.student))
    return 0


def cmd_notify_all(args) -> int:
    session, _ = _load_session(args.state)
    _emit(all_notifications(session))
    return 0


def cmd_explain(args) -> int:
    """Privacy-safe facts about one student's placement, for the
    explain-match skill to narrate. Schedule and config facts only."""
    session, _ = _load_session(args.state)
    student = session.student(args.student)
    for g in session.proposal["groups"]:
        if args.student in g["members"]:
            members = [session.student(sid) for sid in g["members"]]
            shared = group_overlap_slots(members)
            _emit(
                {
                    "student_id": args.student,
                    "group_id": g["group_id"],
                    "group_size": len(members),
                    "shared_slot_count": len(shared),
                    "meeting_slots": g["meeting_slots"],
                    "min_overlap_required": session.config.min_overlap,
                    "status": session.proposal["status"],
                }
            )
            return 0
    reason = next(
        (u["reason"] for u in session.proposal["unplaced"] if u["student_id"] == args.student),
        None,
    )
    _emit({"student_id": args.student, "unplaced": True, "reason": reason})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reflectool")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("intake", help="validate a roster file, report aggregate stats")
    p.add_argument("--roster", required=True)
    p.set_defaults(fn=cmd_intake)

    p = sub.add_parser("match", help="run the matcher, write a proposed session")
    p.add_argument("--roster", required=True)
    p.add_argument("--state", required=True)
    p.add_argument("--min-overlap", type=int, dest="min_overlap")
    p.add_argument("--priority", help="comma-separated factor order")
    p.set_defaults(fn=cmd_match)

    p = sub.add_parser("show", help="print the current proposal")
    p.add_argument("--state", required=True)
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("composition", help="instructor-only aggregate composition view")
    p.add_argument("--state", required=True)
    p.set_defaults(fn=cmd_composition)

    p = sub.add_parser("edit", help="manual instructor edit, re-validated")
    p.add_argument("--state", required=True)
    p.add_argument("--action", required=True, choices=["move", "assign"])
    p.add_argument("--student", required=True)
    p.add_argument("--to-group", required=True, type=int, dest="to_group")
    p.add_argument("--allow-oversize", action="store_true", dest="allow_oversize")
    p.add_argument("--allow-low-overlap", action="store_true", dest="allow_low_overlap")
    p.set_defaults(fn=cmd_edit)

    p = sub.add_parser("approve", help="proposed -> approved")
    p.add_argument("--state", required=True)
    p.set_defaults(fn=cmd_approve)

    p = sub.add_parser("publish", help="approved -> published")
    p.add_argument("--state", required=True)
    p.set_defaults(fn=cmd_publish)

    p = sub.add_parser("student-view", help="one student's own-group notification")
    p.add_argument("--state", required=True)
    p.add_argument("--student", required=True)
    p.set_defaults(fn=cmd_student_view)

    p = sub.add_parser("notify-all", help="every student's notification view")
    p.add_argument("--state", required=True)
    p.set_defaults(fn=cmd_notify_all)

    p = sub.add_parser("explain", help="privacy-safe placement facts for one student")
    p.add_argument("--state", required=True)
    p.add_argument("--student", required=True)
    p.set_defaults(fn=cmd_explain)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except (WorkflowError, ValidationError, KeyError) as e:
        print(json.dumps({"error": str(e)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
