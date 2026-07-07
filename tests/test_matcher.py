import pytest

from reflectool.io_parse import Config, Grid, Student
from reflectool.matcher import match, plan_group_sizes, repair_pass
from reflectool.objective import equity_isolation_count, group_overlap_slots

SMALL_GRID = Grid(days=1, start="08:00", end="10:00", slot_minutes=30)  # 4 slots
SMALL_CONFIG = Config(grid=SMALL_GRID)


def make_student(sid, avail, gender="man", disability="none"):
    return Student(sid, tuple(bool(v) for v in avail), gender, disability)


SPEC_EXAMPLE = [
    make_student("s01", [1, 1, 0, 0], "woman", "adhd"),
    make_student("s02", [1, 1, 1, 0], "woman", "mental_health"),
    make_student("s03", [1, 1, 0, 1], "non_binary", "none"),
    make_student("s04", [0, 0, 1, 1], "man", "none"),
    make_student("s05", [0, 0, 1, 1], "man", "autism"),
    make_student("s06", [0, 1, 1, 1], "man", "undisclosed"),
]


class TestPlanGroupSizes:
    def test_38_gives_six_5s_and_two_4s(self):
        assert plan_group_sizes(38, SMALL_CONFIG) == [5, 5, 5, 5, 5, 5, 4, 4]

    def test_6_gives_two_3s(self):
        assert plan_group_sizes(6, SMALL_CONFIG) == [3, 3]

    def test_7_gives_4_and_3(self):
        assert plan_group_sizes(7, SMALL_CONFIG) == [4, 3]

    def test_never_produces_size_6(self):
        for n in range(3, 200):
            sizes = plan_group_sizes(n, SMALL_CONFIG)
            assert all(3 <= s <= 5 for s in sizes)
            assert sum(sizes) == n

    def test_below_min_size_gives_no_groups(self):
        assert plan_group_sizes(2, SMALL_CONFIG) == []


class TestMatchSpecExample:
    def test_reproduces_spec_partition(self):
        result = match(SPEC_EXAMPLE, SMALL_CONFIG)
        memberships = sorted(sorted(s.student_id for s in g) for g in result.groups)
        assert memberships == [["s01", "s02", "s03"], ["s04", "s05", "s06"]]
        assert result.unplaced == []


class TestHardConstraints:
    def test_group_sizes_in_bounds_and_never_6(self):
        students = [make_student(f"s{i:02d}", [1, 1, 1, 1]) for i in range(38)]
        result = match(students, SMALL_CONFIG)
        for g in result.groups:
            assert 3 <= len(g) <= 5

    def test_every_group_meets_min_overlap(self):
        result = match(SPEC_EXAMPLE, SMALL_CONFIG)
        for g in result.groups:
            assert len(group_overlap_slots(g)) >= SMALL_CONFIG.min_overlap

    def test_every_student_placed_exactly_once(self):
        result = match(SPEC_EXAMPLE, SMALL_CONFIG)
        placed = [s.student_id for g in result.groups for s in g]
        placed += [u["student_id"] for u in result.unplaced]
        assert sorted(placed) == sorted(s.student_id for s in SPEC_EXAMPLE)

    def test_no_overlap_student_goes_unplaced_with_reason(self):
        students = SPEC_EXAMPLE + [make_student("s99", [0, 0, 0, 0])]
        result = match(students, SMALL_CONFIG)
        unplaced_ids = [u["student_id"] for u in result.unplaced]
        assert "s99" in unplaced_ids
        reason = next(u["reason"] for u in result.unplaced if u["student_id"] == "s99")
        assert reason

    def test_38_all_available_gives_8_groups(self):
        students = [make_student(f"s{i:02d}", [1, 1, 1, 1]) for i in range(38)]
        result = match(students, SMALL_CONFIG)
        assert sorted(len(g) for g in result.groups) == [4, 4, 5, 5, 5, 5, 5, 5]


class TestDeterminism:
    def test_same_input_same_output(self):
        r1 = match(SPEC_EXAMPLE, SMALL_CONFIG)
        r2 = match(SPEC_EXAMPLE, SMALL_CONFIG)
        assert [[s.student_id for s in g] for g in r1.groups] == [
            [s.student_id for s in g] for g in r2.groups
        ]

    def test_permuted_input_same_partition(self):
        r1 = match(SPEC_EXAMPLE, SMALL_CONFIG)
        r2 = match(list(reversed(SPEC_EXAMPLE)), SMALL_CONFIG)
        p1 = sorted(sorted(s.student_id for s in g) for g in r1.groups)
        p2 = sorted(sorted(s.student_id for s in g) for g in r2.groups)
        assert p1 == p2


class TestRepairPass:
    def test_swap_fixes_lone_woman_isolation(self):
        w1 = make_student("w1", [1, 1, 1, 1], "woman")
        w2 = make_student("w2", [1, 1, 1, 1], "woman")
        w3 = make_student("w3", [1, 1, 1, 1], "woman")
        m1 = make_student("m1", [1, 1, 1, 1], "man")
        m2 = make_student("m2", [1, 1, 1, 1], "man")
        m3 = make_student("m3", [1, 1, 1, 1], "man")
        bad = [[w1, m1, m2], [w2, w3, m3]]
        repaired = repair_pass(bad, SMALL_CONFIG)
        assert sum(equity_isolation_count(g) for g in repaired) == 0

    def test_repair_never_breaks_min_overlap(self):
        # w1 only shares slots with m1/m2; a swap pairing her with w2/w3 would
        # break min_overlap, so the isolation stays and must not be "fixed".
        w1 = make_student("w1", [1, 1, 0, 0], "woman")
        m1 = make_student("m1", [1, 1, 0, 0], "man")
        m2 = make_student("m2", [1, 1, 0, 0], "man")
        w2 = make_student("w2", [0, 0, 1, 1], "woman")
        w3 = make_student("w3", [0, 0, 1, 1], "woman")
        m3 = make_student("m3", [0, 0, 1, 1], "man")
        groups = [[w1, m1, m2], [w2, w3, m3]]
        repaired = repair_pass(groups, SMALL_CONFIG)
        for g in repaired:
            assert len(group_overlap_slots(g)) >= SMALL_CONFIG.min_overlap

    def test_unavoidable_isolation_is_reported_as_warning(self):
        w1 = make_student("w1", [1, 1, 0, 0], "woman")
        m1 = make_student("m1", [1, 1, 0, 0], "man")
        m2 = make_student("m2", [1, 1, 0, 0], "man")
        w2 = make_student("w2", [0, 0, 1, 1], "woman")
        w3 = make_student("w3", [0, 0, 1, 1], "woman")
        m3 = make_student("m3", [0, 0, 1, 1], "man")
        result = match([w1, m1, m2, w2, w3, m3], SMALL_CONFIG)
        assert any("isolat" in w.lower() for w in result.warnings)


class TestMeetingSlots:
    def test_groups_get_meeting_slot_indices_from_mutual_availability(self):
        result = match(SPEC_EXAMPLE, SMALL_CONFIG)
        for g, slots in zip(result.groups, result.meeting_slots):
            shared = set(group_overlap_slots(g))
            assert slots
            assert set(slots) <= shared
