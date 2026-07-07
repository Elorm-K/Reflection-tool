from reflectool.io_parse import Config, Grid, Student
from reflectool.objective import (
    equity_isolation_count,
    group_overlap_slots,
    group_score,
    homogeneity,
    lone_minority_count,
)


def make_student(sid, avail, gender="man", disability="none"):
    return Student(sid, tuple(bool(v) for v in avail), gender, disability)


CONFIG = Config(grid=Grid(days=1, start="08:00", end="10:00", slot_minutes=30))


class TestGroupOverlap:
    def test_intersection_of_availability(self):
        group = [
            make_student("s1", [1, 1, 1, 0]),
            make_student("s2", [1, 1, 0, 0]),
            make_student("s3", [0, 1, 1, 0]),
        ]
        assert group_overlap_slots(group) == (1,)

    def test_full_overlap(self):
        group = [make_student("s1", [1, 1, 0, 0]), make_student("s2", [1, 1, 0, 0])]
        assert group_overlap_slots(group) == (0, 1)


class TestHomogeneity:
    def test_all_same_known_value_scores_one(self):
        group = [make_student(f"s{i}", [1] * 4, gender="woman") for i in range(3)]
        assert homogeneity(group, "gender") == 1.0

    def test_majority_fraction(self):
        group = [
            make_student("s1", [1] * 4, gender="woman"),
            make_student("s2", [1] * 4, gender="woman"),
            make_student("s3", [1] * 4, gender="man"),
        ]
        assert homogeneity(group, "gender") == 2 / 3

    def test_undisclosed_excluded_from_numerator_and_denominator(self):
        group = [
            make_student("s1", [1] * 4, gender="woman"),
            make_student("s2", [1] * 4, gender="woman"),
            make_student("s3", [1] * 4, gender="undisclosed"),
        ]
        assert homogeneity(group, "gender") == 1.0

    def test_all_undisclosed_is_neutral_none(self):
        group = [make_student("s1", [1] * 4, gender="undisclosed")]
        assert homogeneity(group, "gender") is None


class TestEquityIsolation:
    def test_lone_woman_among_men_counts(self):
        group = [
            make_student("s1", [1] * 4, gender="woman"),
            make_student("s2", [1] * 4, gender="man"),
            make_student("s3", [1] * 4, gender="man"),
        ]
        assert equity_isolation_count(group) == 1

    def test_two_women_together_is_fine(self):
        group = [
            make_student("s1", [1] * 4, gender="woman"),
            make_student("s2", [1] * 4, gender="woman"),
            make_student("s3", [1] * 4, gender="man"),
        ]
        assert equity_isolation_count(group) == 0

    def test_woman_plus_non_binary_protects_both(self):
        group = [
            make_student("s1", [1] * 4, gender="woman"),
            make_student("s2", [1] * 4, gender="non_binary"),
            make_student("s3", [1] * 4, gender="man"),
        ]
        assert equity_isolation_count(group) == 0

    def test_lone_non_binary_counts(self):
        group = [
            make_student("s1", [1] * 4, gender="non_binary"),
            make_student("s2", [1] * 4, gender="man"),
            make_student("s3", [1] * 4, gender="man"),
        ]
        assert equity_isolation_count(group) == 1

    def test_all_women_group_is_fine(self):
        group = [make_student(f"s{i}", [1] * 4, gender="woman") for i in range(3)]
        assert equity_isolation_count(group) == 0

    def test_undisclosed_never_counted_as_isolated(self):
        group = [
            make_student("s1", [1] * 4, gender="undisclosed"),
            make_student("s2", [1] * 4, gender="man"),
            make_student("s3", [1] * 4, gender="man"),
        ]
        assert equity_isolation_count(group) == 0


class TestLoneMinority:
    def test_lone_known_disability_among_nones_counts(self):
        group = [
            make_student("s1", [1] * 4, disability="adhd"),
            make_student("s2", [1] * 4, disability="none"),
            make_student("s3", [1] * 4, disability="none"),
        ]
        assert lone_minority_count(group) == 1

    def test_two_disabled_students_together_fine(self):
        group = [
            make_student("s1", [1] * 4, disability="adhd"),
            make_student("s2", [1] * 4, disability="autism"),
            make_student("s3", [1] * 4, disability="none"),
        ]
        assert lone_minority_count(group) == 0

    def test_undisclosed_never_counted(self):
        group = [
            make_student("s1", [1] * 4, disability="undisclosed"),
            make_student("s2", [1] * 4, disability="none"),
            make_student("s3", [1] * 4, disability="none"),
        ]
        assert lone_minority_count(group) == 0


class TestGroupScore:
    def test_equity_dominates_priority_tiers(self):
        # A group isolating a lone woman scores worse than one that does not,
        # even if the isolating group has better schedule overlap.
        isolating = [
            make_student("s1", [1, 1, 1, 1], gender="woman"),
            make_student("s2", [1, 1, 1, 1], gender="man"),
            make_student("s3", [1, 1, 1, 1], gender="man"),
        ]
        safe = [
            make_student("s4", [1, 1, 0, 0], gender="man"),
            make_student("s5", [1, 1, 0, 0], gender="man"),
            make_student("s6", [1, 1, 0, 0], gender="man"),
        ]
        assert group_score(safe, CONFIG) > group_score(isolating, CONFIG)

    def test_priority_order_controls_tier_order(self):
        # Two groups, identical equity and schedule; one homogeneous on gender,
        # the other on disability. Which wins flips with config.priority.
        gender_homog = [
            make_student("s1", [1, 1, 0, 0], gender="woman", disability="adhd"),
            make_student("s2", [1, 1, 0, 0], gender="woman", disability="none"),
        ]
        disability_homog = [
            make_student("s3", [1, 1, 0, 0], gender="woman", disability="adhd"),
            make_student("s4", [1, 1, 0, 0], gender="man", disability="adhd"),
        ]
        gender_first = Config(grid=CONFIG.grid, priority=("availability", "gender", "disability"))
        disability_first = Config(grid=CONFIG.grid, priority=("availability", "disability", "gender"))
        # disability_homog isolates neither (two women? no: one woman one man -> lone woman!)
        # Use size-2 groups only for scoring comparison; equity differs, so instead
        # compare with equity-neutral compositions:
        gender_homog2 = [
            make_student("s1", [1, 1, 0, 0], gender="woman", disability="adhd"),
            make_student("s2", [1, 1, 0, 0], gender="woman", disability="none"),
        ]
        disability_homog2 = [
            make_student("s3", [1, 1, 0, 0], gender="woman", disability="adhd"),
            make_student("s4", [1, 1, 0, 0], gender="non_binary", disability="adhd"),
        ]
        assert group_score(gender_homog2, gender_first) > group_score(disability_homog2, gender_first)
        assert group_score(disability_homog2, disability_first) > group_score(gender_homog2, disability_first)

    def test_availability_rewards_clearing_min_overlap_not_maximizing(self):
        # Both groups clear min_overlap + buffer; extra shared slots beyond the
        # buffer must not outrank an identity tier below availability.
        many_slots_mixed = [
            make_student("s1", [1, 1, 1, 1], gender="woman"),
            make_student("s2", [1, 1, 1, 1], gender="non_binary"),
            make_student("s3", [1, 1, 1, 1], gender="man"),
        ]
        buffer_homog = [
            make_student("s4", [1, 1, 1, 0], gender="man"),
            make_student("s5", [1, 1, 1, 0], gender="man"),
            make_student("s6", [1, 1, 1, 0], gender="man"),
        ]
        assert group_score(buffer_homog, CONFIG) > group_score(many_slots_mixed, CONFIG)
