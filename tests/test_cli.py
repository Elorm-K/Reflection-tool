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

    def test_edit_low_overlap_override_flag(self, tmp_path, capsys):
        # Two availability blocks: group 1 = s01..s04 (early), group 2 = s05..s07 (late).
        # Moving s01 -> group 2 keeps the source at min_size but shares 0 slots.
        roster = {
            "config": ROSTER["config"],
            "students": [
                {"id": f"s{i:02d}", "name": f"P{i}",
                 "availability": [1, 1, 0, 0] if i <= 4 else [0, 0, 1, 1],
                 "gender": "man", "disability": "none"}
                for i in range(1, 8)
            ],
        }
        roster_path = tmp_path / "roster.json"
        roster_path.write_text(json.dumps(roster))
        state = tmp_path / "session.json"
        run(capsys, "match", "--roster", roster_path, "--state", state)

        code, out = run(capsys, "edit", "--state", state, "--action", "move",
                        "--student", "s01", "--to-group", "2")
        assert code == 1
        assert "allow_low_overlap" in out  # rejection names the override

        code, out = run(capsys, "edit", "--state", state, "--action", "move",
                        "--student", "s01", "--to-group", "2", "--allow-low-overlap")
        assert code == 0
        proposal = json.loads(out)
        target = next(g for g in proposal["groups"] if g["group_id"] == 2)
        assert "s01" in target["members"]
        assert target["meeting_slots"] == []

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

    # ── live edits (published cycles) ──────────────────────────────────────
    def _published_state(self, tmp_path, capsys):
        """8 fully-available students -> any move is bounded only by size."""
        roster = {
            "config": ROSTER["config"],
            "students": [
                {"id": f"s{i:02d}", "name": f"P{i}", "availability": [1, 1, 1, 1],
                 "gender": "man" if i % 2 else "woman", "disability": "none"}
                for i in range(1, 9)
            ],
        }
        roster_path = tmp_path / "roster.json"
        roster_path.write_text(json.dumps(roster))
        state = tmp_path / "session.json"
        run(capsys, "match", "--roster", roster_path, "--state", state)
        run(capsys, "approve", "--state", state)
        run(capsys, "publish", "--state", state)
        return state

    def test_live_edit_moves_a_student_on_a_published_cycle(self, tmp_path, capsys):
        state = self._published_state(tmp_path, capsys)
        _, out = run(capsys, "show", "--state", state)
        groups = json.loads(out)["groups"]
        mover = groups[0]["members"][0]
        target = groups[1]["group_id"]

        code, out = run(capsys, "edit", "--live", "--state", state,
                        "--action", "move", "--student", mover, "--to-group", target)
        assert code == 0
        proposal = json.loads(out)
        assert proposal["status"] == "published"  # status never changes
        moved_into = next(g for g in proposal["groups"] if g["group_id"] == target)
        assert mover in moved_into["members"]

        saved = json.loads(state.read_text())
        assert any(entry.startswith(f"live-move {mover}") for entry in saved["audit_log"])

    def test_live_edit_requires_the_live_flag(self, tmp_path, capsys):
        state = self._published_state(tmp_path, capsys)
        _, out = run(capsys, "show", "--state", state)
        groups = json.loads(out)["groups"]
        code, out = run(capsys, "edit", "--state", state, "--action", "move",
                        "--student", groups[0]["members"][0],
                        "--to-group", groups[1]["group_id"])
        assert code == 1
        assert "only allowed while status is 'proposed'" in out

    def test_live_edit_rejected_before_publish(self, paths, capsys):
        roster, state = paths
        run(capsys, "match", "--roster", roster, "--state", state)
        code, out = run(capsys, "edit", "--live", "--state", state, "--action", "move",
                        "--student", "s01", "--to-group", 2)
        assert code == 1
        assert "live edits are only allowed while status is 'published'" in out

        run(capsys, "approve", "--state", state)
        code, out = run(capsys, "edit", "--live", "--state", state, "--action", "move",
                        "--student", "s01", "--to-group", 2)
        assert code == 1
        assert "live edits are only allowed while status is 'published'" in out

    def test_live_edit_revalidates_size_bounds(self, tmp_path, capsys):
        state = self._published_state(tmp_path, capsys)
        _, out = run(capsys, "show", "--state", state)
        groups = json.loads(out)["groups"]
        # Fill one group past max_size by moving members into it one at a time;
        # either a size bound or the source's min_size stops it.
        target = groups[0]["group_id"]
        donors = [m for g in groups if g["group_id"] != target for m in g["members"]]
        code = 0
        for donor in donors:
            code, out = run(capsys, "edit", "--live", "--state", state, "--action", "move",
                            "--student", donor, "--to-group", target)
            if code == 1:
                break
        assert code == 1
        assert "violates size bounds" in out
        assert "allow_oversize" in out

    def test_live_assign_places_an_unplaced_student(self, tmp_path, capsys):
        # s07 shares no slots with anyone -> unplaced by the matcher.
        roster = {
            "config": ROSTER["config"],
            "students": [
                {"id": f"s{i:02d}", "name": f"P{i}",
                 "availability": [1, 1, 1, 1] if i <= 6 else [0, 0, 0, 0],
                 "gender": "man", "disability": "none"}
                for i in range(1, 8)
            ],
        }
        roster_path = tmp_path / "roster.json"
        roster_path.write_text(json.dumps(roster))
        state = tmp_path / "session.json"
        run(capsys, "match", "--roster", roster_path, "--state", state)
        _, out = run(capsys, "show", "--state", state)
        proposal = json.loads(out)
        assert [u["student_id"] for u in proposal["unplaced"]] == ["s07"]
        target = proposal["groups"][0]["group_id"]

        run(capsys, "approve", "--state", state)
        run(capsys, "publish", "--state", state)
        code, out = run(capsys, "edit", "--live", "--state", state, "--action", "assign",
                        "--student", "s07", "--to-group", target,
                        "--allow-low-overlap")
        assert code == 0
        saved = json.loads(state.read_text())
        assert any(entry.startswith("live-assign") for entry in saved["audit_log"])
