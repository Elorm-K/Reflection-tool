import json

import pytest

from reflectool.cli import main

ROSTER = {
    "config": {
        "grid": {"days": 1, "start": "08:00", "end": "10:00", "slot_minutes": 30},
        "min_overlap": 2,
    },
    "students": [
        {"id": "s01", "name": "Ada", "availability": [1, 1, 0, 0], "gender": "woman", "disability": "adhd"},
        {"id": "s02", "name": "Bel", "availability": [1, 1, 1, 0], "gender": "woman", "disability": "mental_health"},
        {"id": "s03", "name": "Cam", "availability": [1, 1, 0, 1], "gender": "non_binary", "disability": "none"},
        {"id": "s04", "name": "Dev", "availability": [0, 0, 1, 1], "gender": "man", "disability": "none"},
        {"id": "s05", "name": "Eli", "availability": [0, 0, 1, 1], "gender": "man", "disability": "autism"},
        {"id": "s06", "name": "Fox", "availability": [0, 1, 1, 1], "gender": "man", "disability": "prefer_not_to_disclose"},
    ],
}


@pytest.fixture
def paths(tmp_path):
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps(ROSTER))
    return roster, tmp_path / "session.json"


def run(capsys, *args):
    code = main([str(a) for a in args])
    out = capsys.readouterr().out
    return code, out


class TestCli:
    def test_intake_reports_counts_not_individuals(self, paths, capsys):
        roster, _ = paths
        code, out = run(capsys, "intake", "--roster", roster)
        assert code == 0
        report = json.loads(out)
        assert report["students"] == 6
        assert report["gender_counts"]["woman"] == 2
        assert report["disability_counts"]["undisclosed"] == 1
        assert "s01" not in out  # aggregate only, no per-student identity dump

    def test_match_writes_session_and_prints_proposal(self, paths, capsys):
        roster, state = paths
        code, out = run(capsys, "match", "--roster", roster, "--state", state)
        assert code == 0
        proposal = json.loads(out)
        assert proposal["status"] == "proposed"
        assert len(proposal["groups"]) == 2
        assert state.exists()

    def test_full_lifecycle(self, paths, capsys):
        roster, state = paths
        run(capsys, "match", "--roster", roster, "--state", state)
        code, out = run(capsys, "composition", "--state", state)
        assert code == 0
        assert "gender_composition" in out
        code, _ = run(capsys, "approve", "--state", state)
        assert code == 0
        code, _ = run(capsys, "publish", "--state", state)
        assert code == 0
        code, out = run(capsys, "student-view", "--state", state, "--student", "s01")
        assert code == 0
        view = json.loads(out)
        assert view["members"] == ["Ada", "Bel", "Cam"]
        assert "gender" not in out

    def test_publish_before_approve_fails(self, paths, capsys):
        roster, state = paths
        run(capsys, "match", "--roster", roster, "--state", state)
        code, out = run(capsys, "publish", "--state", state)
        assert code == 1
        assert "approved" in out

    def test_invalid_edit_fails_with_reason(self, paths, capsys):
        roster, state = paths
        run(capsys, "match", "--roster", roster, "--state", state)
        code, out = run(capsys, "edit", "--state", state, "--action", "move", "--student", "s01", "--to-group", "2")
        assert code == 1

    def test_student_view_before_publish_fails(self, paths, capsys):
        roster, state = paths
        run(capsys, "match", "--roster", roster, "--state", state)
        code, out = run(capsys, "student-view", "--state", state, "--student", "s01")
        assert code == 1
        assert "published" in out

    def test_explain_gives_schedule_facts_only(self, paths, capsys):
        roster, state = paths
        run(capsys, "match", "--roster", roster, "--state", state)
        code, out = run(capsys, "explain", "--state", state, "--student", "s01")
        assert code == 0
        facts = json.loads(out)
        assert facts["group_id"] == 1
        assert facts["shared_slot_count"] >= 2
        assert "gender" not in out and "disability" not in out

    def test_priority_override_flag(self, paths, capsys):
        roster, state = paths
        code, out = run(
            capsys, "match", "--roster", roster, "--state", state,
            "--priority", "availability,disability,gender",
        )
        assert code == 0
        assert json.loads(out)["status"] == "proposed"
