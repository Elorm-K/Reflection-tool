import pytest

from reflectool.io_parse import Config, Grid, Student
from reflectool.matcher import match
from reflectool.output_format import assert_no_demographics, build_proposal
from reflectool.notify import PreApprovalLeak, all_notifications, student_view
from reflectool.review_workflow import Session, approve, publish

SMALL_GRID = Grid(days=1, start="08:00", end="10:00", slot_minutes=30)
SMALL_CONFIG = Config(grid=SMALL_GRID)


def make_student(sid, avail, gender="man", disability="none", name=""):
    return Student(sid, tuple(bool(v) for v in avail), gender, disability, name or sid.upper())


def make_session():
    students = [
        make_student("s01", [1, 1, 0, 0], "woman", "adhd", "Ada"),
        make_student("s02", [1, 1, 1, 0], "woman", "mental_health", "Bel"),
        make_student("s03", [1, 1, 0, 1], "non_binary", "none", "Cam"),
        make_student("s04", [0, 0, 1, 1], "man", "none", "Dev"),
        make_student("s05", [0, 0, 1, 1], "man", "autism", "Eli"),
        make_student("s06", [0, 1, 1, 1], "man", "undisclosed", "Fox"),
    ]
    result = match(students, SMALL_CONFIG)
    proposal = build_proposal(result, SMALL_CONFIG)
    return Session(roster=students, config=SMALL_CONFIG, proposal=proposal)


class TestPreApprovalLeak:
    def test_no_view_while_proposed(self):
        with pytest.raises(PreApprovalLeak):
            student_view(make_session(), "s01")

    def test_no_view_while_approved(self):
        session = make_session()
        approve(session)
        with pytest.raises(PreApprovalLeak):
            student_view(session, "s01")


class TestPublishedView:
    def make_published(self):
        session = make_session()
        approve(session)
        publish(session)
        return session

    def test_student_sees_own_group_number_members_and_slots(self):
        view = student_view(self.make_published(), "s01")
        assert view["group_number"] == 1
        assert view["members"] == ["Ada", "Bel", "Cam"]
        assert view["meeting_slots"] == ["Mon-08:00", "Mon-08:30"]

    def test_view_has_no_demographics(self):
        assert_no_demographics(student_view(self.make_published(), "s01"))

    def test_view_contains_no_other_groups_data(self):
        view = student_view(self.make_published(), "s01")
        flat = str(view)
        for other in ("Dev", "Eli", "Fox", "s04", "s05", "s06"):
            assert other not in flat

    def test_all_notifications_covers_every_placed_student(self):
        session = self.make_published()
        notes = all_notifications(session)
        assert sorted(notes) == ["s01", "s02", "s03", "s04", "s05", "s06"]

    def test_unknown_student_rejected(self):
        with pytest.raises(KeyError):
            student_view(self.make_published(), "s42")
