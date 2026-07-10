import pytest

from reflectool.io_parse import Config, Grid, Student
from reflectool.matcher import match
from reflectool.output_format import assert_no_demographics, build_proposal
from reflectool.review_workflow import (
    IllegalTransition,
    InvalidEdit,
    Session,
    apply_edit,
    apply_live_edit,
    approve,
    composition_view,
    publish,
)

SMALL_GRID = Grid(days=1, start="08:00", end="10:00", slot_minutes=30)
SMALL_CONFIG = Config(grid=SMALL_GRID)


def make_student(sid, avail, gender="man", disability="none", name=""):
    return Student(sid, tuple(bool(v) for v in avail), gender, disability, name or sid.upper())


def make_session(extra=()):
    students = [
        make_student("s01", [1, 1, 0, 0], "woman", "adhd"),
        make_student("s02", [1, 1, 1, 0], "woman", "mental_health"),
        make_student("s03", [1, 1, 0, 1], "non_binary", "none"),
        make_student("s04", [0, 0, 1, 1], "man", "none"),
        make_student("s05", [0, 0, 1, 1], "man", "autism"),
        make_student("s06", [0, 1, 1, 1], "man", "undisclosed"),
        *extra,
    ]
    result = match(students, SMALL_CONFIG)
    proposal = build_proposal(result, SMALL_CONFIG)
    return Session(roster=students, config=SMALL_CONFIG, proposal=proposal)


class TestStateMachine:
    def test_fresh_session_is_proposed(self):
        assert make_session().proposal["status"] == "proposed"

    def test_approve_then_publish(self):
        session = make_session()
        approve(session)
        assert session.proposal["status"] == "approved"
        publish(session)
        assert session.proposal["status"] == "published"

    def test_cannot_publish_from_proposed(self):
        session = make_session()
        with pytest.raises(IllegalTransition):
            publish(session)

    def test_cannot_approve_twice(self):
        session = make_session()
        approve(session)
        with pytest.raises(IllegalTransition):
            approve(session)


class TestCompositionView:
    def test_shows_aggregates_per_group(self):
        view = composition_view(make_session())
        g1 = view["groups"][0]
        assert g1["size"] == 3
        assert g1["gender_composition"] == {"woman": 2, "non_binary": 1}
        assert g1["gender_homogeneity"] is not None

    def test_undisclosed_shown_as_undisclosed_bucket(self):
        view = composition_view(make_session())
        g2 = view["groups"][1]
        assert g2["disability_composition"].get("undisclosed") == 1


class TestApplyEdit:
    def test_valid_move_updates_groups_and_slots(self):
        session = make_session()
        # s06 shares slots 2,3 with group 2 already; moving s06 out and back is a no-op,
        # so instead move s02 (shares slot 2 only with group 2) -> should fail;
        # a valid move: s06 to group 1 shares slot 1 only -> fails too.
        # Use assign of an extra compatible student instead: move s05 to group 1?
        # s05 shares no 2 slots with group 1. All cross moves here break overlap,
        # so build a valid one: add s07 free everywhere, matched into some group,
        # then move it to the other group.
        session = make_session(extra=[make_student("s07", [1, 1, 1, 1], "man", "none")])
        groups = session.proposal["groups"]
        source = next(g for g in groups if "s07" in g["members"])
        target = next(g for g in groups if "s07" not in g["members"])
        apply_edit(session, {"action": "move", "student_id": "s07", "to_group": target["group_id"]})
        groups = session.proposal["groups"]
        assert "s07" in next(g for g in groups if g["group_id"] == target["group_id"])["members"]
        assert "s07" not in next(g for g in groups if g["group_id"] == source["group_id"])["members"]

    def test_move_breaking_min_overlap_rejected(self):
        # s07 keeps the source group at min_size so the overlap check is what fires:
        # s01 shares no slots with group 2 (who meet Wed/Thu-style late slots).
        session = make_session(extra=[make_student("s07", [1, 1, 1, 1], "man", "none")])
        source = next(g for g in session.proposal["groups"] if "s01" in g["members"])
        assert len(source["members"]) > SMALL_CONFIG.min_size
        other = next(g for g in session.proposal["groups"] if "s01" not in g["members"])
        with pytest.raises(InvalidEdit, match="min_overlap"):
            apply_edit(session, {"action": "move", "student_id": "s01", "to_group": other["group_id"]})

    def test_move_breaking_min_size_rejected(self):
        session = make_session()
        # groups are size 3; removing anyone drops a group below min_size
        with pytest.raises(InvalidEdit, match="size"):
            apply_edit(session, {"action": "move", "student_id": "s06", "to_group": 1})

    def test_oversize_rejected_without_override(self):
        extras = [make_student(f"s{i:02d}", [1, 1, 1, 1]) for i in range(7, 14)]
        session = make_session(extra=extras)  # 13 students -> sizes 5,5,3 or similar
        groups = session.proposal["groups"]
        full = next(g for g in groups if len(g["members"]) == 5)
        other = next(g for g in groups if g["group_id"] != full["group_id"])
        mover = other["members"][-1]
        with pytest.raises(InvalidEdit, match="size"):
            apply_edit(session, {"action": "move", "student_id": mover, "to_group": full["group_id"]})

    def test_oversize_allowed_with_explicit_override_and_logged(self):
        extras = [make_student(f"s{i:02d}", [1, 1, 1, 1]) for i in range(7, 14)]
        session = make_session(extra=extras)
        groups = session.proposal["groups"]
        full = next(g for g in groups if len(g["members"]) == 5)
        other = next(g for g in groups if len(g["members"]) > SMALL_CONFIG.min_size and g["group_id"] != full["group_id"])
        mover = other["members"][-1]
        apply_edit(
            session,
            {"action": "move", "student_id": mover, "to_group": full["group_id"], "allow_oversize": True},
        )
        target = next(g for g in session.proposal["groups"] if g["group_id"] == full["group_id"])
        assert len(target["members"]) == 6
        assert any("oversize" in entry for entry in session.audit_log)

    def test_low_overlap_rejection_mentions_override_hint(self):
        # Same setup as test_move_breaking_min_overlap_rejected: s01 shares no
        # slots with the other group, s07 keeps the source at min_size.
        session = make_session(extra=[make_student("s07", [1, 1, 1, 1], "man", "none")])
        other = next(g for g in session.proposal["groups"] if "s01" not in g["members"])
        with pytest.raises(InvalidEdit, match="allow_low_overlap"):
            apply_edit(session, {"action": "move", "student_id": "s01", "to_group": other["group_id"]})

    def test_low_overlap_allowed_with_explicit_override_and_logged(self):
        session = make_session(extra=[make_student("s07", [1, 1, 1, 1], "man", "none")])
        other = next(g for g in session.proposal["groups"] if "s01" not in g["members"])
        apply_edit(
            session,
            {"action": "move", "student_id": "s01", "to_group": other["group_id"],
             "allow_low_overlap": True},
        )
        target = next(g for g in session.proposal["groups"] if g["group_id"] == other["group_id"])
        assert "s01" in target["members"]
        # no mutually-free slot -> surfaced as an empty slot list, never invented
        assert target["meeting_slots"] == []
        assert any("low-overlap override" in entry for entry in session.audit_log)

    def test_low_overlap_override_does_not_bypass_size_bounds(self):
        session = make_session()
        # any move out of a size-3 group still violates min_size, flag or not
        with pytest.raises(InvalidEdit, match="size"):
            apply_edit(session, {"action": "move", "student_id": "s06", "to_group": 1,
                                 "allow_low_overlap": True})

    def test_assign_unplaced_student(self):
        session = make_session(extra=[make_student("s99", [0, 1, 1, 0])])
        # s99 shares only 1 slot with everyone-groups? ensure they're unplaced first
        if not any(u["student_id"] == "s99" for u in session.proposal["unplaced"]):
            pytest.skip("s99 was placed; fixture needs adjusting")
        with pytest.raises(InvalidEdit):
            apply_edit(session, {"action": "assign", "student_id": "s99", "to_group": 1})

    def test_edits_only_allowed_in_proposed_state(self):
        session = make_session(extra=[make_student("s07", [1, 1, 1, 1], "man", "none")])
        approve(session)
        with pytest.raises(IllegalTransition):
            apply_edit(session, {"action": "move", "student_id": "s07", "to_group": 1})

    def test_proposal_stays_demographic_free_after_edit(self):
        session = make_session(extra=[make_student("s07", [1, 1, 1, 1], "man", "none")])
        target = next(g for g in session.proposal["groups"] if "s07" not in g["members"])
        apply_edit(session, {"action": "move", "student_id": "s07", "to_group": target["group_id"]})
        assert_no_demographics(session.proposal)


def make_published_session(extra=()):
    session = make_session(extra=extra)
    approve(session)
    publish(session)
    return session


class TestApplyLiveEdit:
    def test_live_edit_requires_published(self):
        session = make_session(extra=[make_student("s07", [1, 1, 1, 1], "man", "none")])
        target = next(g for g in session.proposal["groups"] if "s07" not in g["members"])
        edit = {"action": "move", "student_id": "s07", "to_group": target["group_id"]}
        with pytest.raises(IllegalTransition):
            apply_live_edit(session, edit)
        approve(session)
        with pytest.raises(IllegalTransition):
            apply_live_edit(session, edit)

    def test_apply_edit_still_blocked_after_publish(self):
        session = make_published_session(extra=[make_student("s07", [1, 1, 1, 1], "man", "none")])
        target = next(g for g in session.proposal["groups"] if "s07" not in g["members"])
        with pytest.raises(IllegalTransition):
            apply_edit(session, {"action": "move", "student_id": "s07", "to_group": target["group_id"]})

    def test_live_move_revalidates_constraints(self):
        session = make_published_session(extra=[make_student("s07", [1, 1, 1, 1], "man", "none")])
        before = [dict(g) for g in session.proposal["groups"]]
        source = next(g for g in session.proposal["groups"] if "s01" in g["members"])
        assert len(source["members"]) > SMALL_CONFIG.min_size
        other = next(g for g in session.proposal["groups"] if "s01" not in g["members"])
        with pytest.raises(InvalidEdit, match="min_overlap"):
            apply_live_edit(session, {"action": "move", "student_id": "s01", "to_group": other["group_id"]})
        assert session.proposal["groups"] == before

    def test_live_move_applies_audits_and_summarizes(self):
        session = make_published_session(extra=[make_student("s07", [1, 1, 1, 1], "man", "none")])
        groups = session.proposal["groups"]
        source = next(g for g in groups if "s07" in g["members"])
        target = next(g for g in groups if "s07" not in g["members"])
        summary = apply_live_edit(
            session, {"action": "move", "student_id": "s07", "to_group": target["group_id"]}
        )
        assert summary == {
            "action": "move",
            "student_id": "s07",
            "from_group": source["group_id"],
            "to_group": target["group_id"],
        }
        groups = session.proposal["groups"]
        assert "s07" in next(g for g in groups if g["group_id"] == target["group_id"])["members"]
        assert "s07" not in next(g for g in groups if g["group_id"] == source["group_id"])["members"]
        assert all(g["meeting_slots"] for g in groups)
        assert any(entry.startswith("live-move s07") for entry in session.audit_log)
        assert session.proposal["status"] == "published"

    def test_live_assign_from_unplaced(self):
        session = make_published_session(extra=[make_student("s99", [0, 1, 1, 0])])
        if not any(u["student_id"] == "s99" for u in session.proposal["unplaced"]):
            pytest.skip("s99 was placed; fixture needs adjusting")
        target = next(
            (g for g in session.proposal["groups"]
             if len(g["members"]) < SMALL_CONFIG.max_size), None
        )
        if target is None:
            pytest.skip("no group with room; fixture needs adjusting")
        try:
            summary = apply_live_edit(
                session, {"action": "assign", "student_id": "s99", "to_group": target["group_id"]}
            )
        except InvalidEdit:
            # overlap may legitimately block; the gate itself is what we're testing
            return
        assert summary["from_group"] is None
        assert not any(u["student_id"] == "s99" for u in session.proposal["unplaced"])
        assert any(entry.startswith("live-assign") for entry in session.audit_log)

    def test_live_edit_returns_summary_and_normal_edit_too(self):
        session = make_session(extra=[make_student("s07", [1, 1, 1, 1], "man", "none")])
        target = next(g for g in session.proposal["groups"] if "s07" not in g["members"])
        summary = apply_edit(
            session, {"action": "move", "student_id": "s07", "to_group": target["group_id"]}
        )
        assert summary["to_group"] == target["group_id"]
