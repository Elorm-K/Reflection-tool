"""Edge-case fixtures behave as their _note fields promise."""

import json
import subprocess
import sys
from pathlib import Path

from reflectool.cli import main
from reflectool.io_parse import parse_config, parse_roster
from reflectool.matcher import match
from reflectool.objective import equity_isolation_count

DATA = Path(__file__).parent.parent / "data"


def load(path):
    data = json.loads(path.read_text())
    config = parse_config(data["config"])
    return parse_roster(data["students"], config), config


class TestEdgeCaseFixtures:
    def test_no_overlap_student_lands_unplaced(self):
        students, config = load(DATA / "edge_cases" / "no_overlap_student.json")
        result = match(students, config)
        assert [u["student_id"] for u in result.unplaced] == ["s99"]

    def test_all_same_gender_groups_on_schedule(self):
        students, config = load(DATA / "edge_cases" / "all_same_gender.json")
        result = match(students, config)
        assert len(result.groups) == 2
        assert result.unplaced == []
        assert result.warnings == []

    def test_lone_minority_repair_never_isolates(self):
        students, config = load(DATA / "edge_cases" / "lone_minority_repair.json")
        result = match(students, config)
        assert sum(equity_isolation_count(g) for g in result.groups) == 0
        memberships = sorted(sorted(s.student_id for s in g) for g in result.groups)
        assert memberships == [["m01", "m02", "m03"], ["w01", "w02", "w03"]]

    def test_injection_text_is_normalized_data(self):
        students, config = load(DATA / "edge_cases" / "injection_in_survey.json")
        s03 = next(s for s in students if s.student_id == "s03")
        assert s03.gender.startswith("ignore_all_previous_instructions")
        result = match(students, config)
        assert result.unplaced == []  # matched normally as a distinct open-set value

    def test_sparse_high_min_overlap_leaves_many_unplaced(self):
        students, config = load(DATA / "edge_cases" / "sparse_high_min_overlap.json")
        result = match(students, config)
        assert len(result.unplaced) >= 4

    def test_demo_roster_reproduces_spec_proposal(self, tmp_path, capsys):
        state = tmp_path / "s.json"
        code = main(["match", "--roster", str(DATA / "demo_roster_6.json"), "--state", str(state)])
        assert code == 0
        proposal = json.loads(capsys.readouterr().out)
        assert [g["members"] for g in proposal["groups"]] == [
            ["s01", "s02", "s03"],
            ["s04", "s05", "s06"],
        ]


class TestGeneratorDeterminism:
    def test_same_seed_byte_identical(self):
        script = str(DATA / "generate_roster.py")
        runs = [
            subprocess.run(
                [sys.executable, script, "--n", "12", "--seed", "5"],
                capture_output=True, text=True, check=True,
            ).stdout
            for _ in range(2)
        ]
        assert runs[0] == runs[1]

    def test_checked_in_38_fixture_matches_seed_0(self):
        script = str(DATA / "generate_roster.py")
        out = subprocess.run(
            [sys.executable, script, "--n", "38", "--seed", "0"],
            capture_output=True, text=True, check=True,
        ).stdout
        assert json.loads(out) == json.loads((DATA / "roster_38.json").read_text())
