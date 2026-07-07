"""Builds the privacy-safe proposal structure (spec section 4.5).

The proposal carries group assignments and meeting times and nothing else:
no gender, no disability, directly or by implication. assert_no_demographics
is called before anything is emitted, so the privacy invariant is enforced
in code, not just by convention.
"""

from __future__ import annotations

from .io_parse import Config
from .matcher import MatchResult

DEMOGRAPHIC_KEYS = {"gender", "disability"}


class PrivacyViolation(AssertionError):
    pass


def assert_no_demographics(obj, path: str = "$") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in DEMOGRAPHIC_KEYS:
                raise PrivacyViolation(f"demographic key {key!r} at {path}")
            assert_no_demographics(value, f"{path}.{key}")
    elif isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            assert_no_demographics(item, f"{path}[{i}]")


def build_proposal(result: MatchResult, config: Config) -> dict:
    proposal = {
        "status": "proposed",
        "groups": [
            {
                "group_id": i,
                "members": [s.student_id for s in group],
                "meeting_slots": [config.grid.slot_label(idx) for idx in slots],
            }
            for i, (group, slots) in enumerate(
                zip(result.groups, result.meeting_slots), start=1
            )
        ],
        "unplaced": list(result.unplaced),
        "warnings": list(result.warnings),
    }
    assert_no_demographics(proposal)
    return proposal
