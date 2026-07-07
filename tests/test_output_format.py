import pytest

from reflectool.io_parse import Config, Grid, Student
from reflectool.matcher import match
from reflectool.output_format import PrivacyViolation, assert_no_demographics, build_proposal

SMALL_GRID = Grid(days=1, start="08:00", end="10:00", slot_minutes=30)
SMALL_CONFIG = Config(grid=SMALL_GRID)


def make_student(sid, avail, gender="man", disability="none"):
    return Student(sid, tuple(bool(v) for v in avail), gender, disability)


STUDENTS = [
    make_student("s01", [1, 1, 0, 0], "woman", "adhd"),
    make_student("s02", [1, 1, 1, 0], "woman", "mental_health"),
    make_student("s03", [1, 1, 0, 1], "non_binary", "none"),
    make_student("s04", [0, 0, 1, 1], "man", "none"),
    make_student("s05", [0, 0, 1, 1], "man", "autism"),
    make_student("s06", [0, 1, 1, 1], "man", "undisclosed"),
]


class TestBuildProposal:
    def make_proposal(self):
        return build_proposal(match(STUDENTS, SMALL_CONFIG), SMALL_CONFIG)

    def test_status_is_proposed(self):
        assert self.make_proposal()["status"] == "proposed"

    def test_group_ids_are_plain_sequence(self):
        proposal = self.make_proposal()
        assert [g["group_id"] for g in proposal["groups"]] == list(
            range(1, len(proposal["groups"]) + 1)
        )

    def test_members_are_ids_and_slots_are_labels(self):
        proposal = self.make_proposal()
        g1 = proposal["groups"][0]
        assert g1["members"] == ["s01", "s02", "s03"]
        assert g1["meeting_slots"] == ["Mon-08:00", "Mon-08:30"]

    def test_no_demographic_keys_anywhere(self):
        proposal = self.make_proposal()
        assert_no_demographics(proposal)  # must not raise

    def test_unplaced_and_warnings_carried_through(self):
        proposal = self.make_proposal()
        assert proposal["unplaced"] == []
        assert "warnings" in proposal


class TestPrivacyGuard:
    def test_rejects_gender_key_at_any_depth(self):
        with pytest.raises(PrivacyViolation):
            assert_no_demographics({"groups": [{"members": [{"gender": "woman"}]}]})

    def test_rejects_disability_key(self):
        with pytest.raises(PrivacyViolation):
            assert_no_demographics({"disability": "adhd"})

    def test_accepts_clean_structure(self):
        assert_no_demographics({"groups": [{"group_id": 1, "members": ["s01"]}]})
