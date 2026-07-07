"""Bridge between web storage and the reflectool core.

The per-cycle `session_json` blob uses the exact same shape the CLI writes to
state/session.json ({raw_students, config, proposal, audit_log}), so the core
functions — and the CLI itself, pointed at an exported blob — see one format.
"""

import json
import sqlite3

from reflectool.io_parse import Config, parse_config, parse_roster
from reflectool.review_workflow import Session

from . import repo


def config_to_dict(config: Config) -> dict:
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


def normalize_config(raw: dict | None) -> dict:
    """Validate raw config via parse_config and return its canonical dict."""
    return config_to_dict(parse_config(raw))


def config_out(config_dict: dict) -> dict:
    """Config as served to clients: grid annotated with num_slots."""
    config = parse_config(config_dict)
    out = config_to_dict(config)
    out["grid"]["num_slots"] = config.grid.num_slots
    return out


def grid_out(config_dict: dict) -> dict:
    return config_out(config_dict)["grid"]


def assemble_raw_students(db: sqlite3.Connection, cycle_id: int) -> list[dict]:
    """Build the roster the matcher sees from stored submissions.

    Only students who submitted availability are included; the instructor sees
    who is missing via roster-status before matching.
    """
    raw = []
    for sub in repo.list_submissions(db, cycle_id):
        if sub["availability"] is None:
            continue
        raw.append(
            {
                "id": sub["student_ext_id"],
                "name": sub["name"],
                "availability": sub["availability"],
                "gender": sub["gender"],
                "disability": sub["disability"],
            }
        )
    return raw


def save_session(db: sqlite3.Connection, cycle_id: int, session: Session,
                 raw_students: list[dict]) -> None:
    blob = {
        "raw_students": raw_students,
        "config": config_to_dict(session.config),
        "proposal": session.proposal,
        "audit_log": session.audit_log,
    }
    repo.update_cycle(db, cycle_id, session_json=json.dumps(blob),
                      status=session.proposal["status"])


def load_session(cycle: dict) -> tuple[Session, list[dict]]:
    data = json.loads(cycle["session_json"])
    config = parse_config(data["config"])
    roster = parse_roster(data["raw_students"], config)
    session = Session(
        roster=roster,
        config=config,
        proposal=data["proposal"],
        audit_log=data["audit_log"],
    )
    return session, data["raw_students"]
