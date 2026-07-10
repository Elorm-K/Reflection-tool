"""Review board, composition, and manual edits over HTTP."""

import pytest

pytest.importorskip("fastapi")

from test_auth import make_class, register_and_login
from test_submissions import join, make_cycle

SMALL_GRID = {"days": 1, "start": "08:00", "end": "10:00", "slot_minutes": 30}


@pytest.fixture()
def ten(client):
    """Ten students, all fully available -> two groups of five. Any move needs
    allow_oversize on the target; sources stay >= min_size."""
    headers = register_and_login(client)
    cls = make_class(
        client, headers,
        roster=[{"student_id": f"s{i:02d}", "name": f"S{i}"} for i in range(1, 11)],
    )
    cycle = make_cycle(client, headers, cls["id"],
                       config={"grid": SMALL_GRID, "min_overlap": 1})
    for i in range(1, 11):
        s = join(client, cls, f"s{i:02d}")
        client.put("/api/me/availability", json={"slots": [1, 1, 1, 1]}, headers=s)
        if i == 1:
            client.put("/api/me/survey",
                       json={"gender": "woman", "disability": "adhd"}, headers=s)
    proposal = client.post(f"/api/cycles/{cycle['id']}/match", headers=headers).json()
    assert sorted(len(g["members"]) for g in proposal["groups"]) == [5, 5]
    return {"headers": headers, "cls": cls, "cycle": cycle, "proposal": proposal}


# --- review board ---------------------------------------------------------------

def test_review_board_includes_per_student_demographics(client, ten):
    resp = client.get(f"/api/cycles/{ten['cycle']['id']}/review-board",
                      headers=ten["headers"])
    assert resp.status_code == 200
    board = resp.json()
    assert board["proposal"]["status"] == "proposed"
    s01 = board["students"]["s01"]
    assert s01["name"] == "S1"
    assert s01["gender"] == "woman"
    assert s01["disability"] == "adhd"
    assert s01["free_slot_count"] == 4
    assert s01["availability"] == [True, True, True, True]
    # undisclosed students carry the neutral slug, never a blank guess
    assert board["students"]["s02"]["gender"] == "undisclosed"


def test_review_board_requires_instructor(client, ten):
    s = join(client, ten["cls"], "s01")
    resp = client.get(f"/api/cycles/{ten['cycle']['id']}/review-board", headers=s)
    assert resp.status_code == 401


def test_review_board_stamps_reviewed_rev(client, ten):
    cid = ten["cycle"]["id"]
    cycle = client.get(f"/api/cycles/{cid}", headers=ten["headers"]).json()
    assert cycle["reviewed_rev"] == -1
    client.get(f"/api/cycles/{cid}/review-board", headers=ten["headers"])
    cycle = client.get(f"/api/cycles/{cid}", headers=ten["headers"]).json()
    assert cycle["reviewed_rev"] == cycle["proposal_rev"]


def test_composition_view_aggregates_and_stamps(client, ten):
    cid = ten["cycle"]["id"]
    resp = client.get(f"/api/cycles/{cid}/composition", headers=ten["headers"])
    assert resp.status_code == 200
    comp = resp.json()
    assert len(comp["groups"]) == 2
    g_with_s01 = next(
        g for g, pg in zip(comp["groups"], ten["proposal"]["groups"])
        if "s01" in pg["members"]
    )
    assert g_with_s01["gender_composition"]["woman"] == 1
    cycle = client.get(f"/api/cycles/{cid}", headers=ten["headers"]).json()
    assert cycle["reviewed_rev"] == cycle["proposal_rev"]


# --- edits ------------------------------------------------------------------------

def test_valid_move_needs_oversize_confirmation(client, ten):
    cid = ten["cycle"]["id"]
    student = ten["proposal"]["groups"][0]["members"][0]
    target = ten["proposal"]["groups"][1]["group_id"]

    resp = client.post(
        f"/api/cycles/{cid}/edits",
        json={"action": "move", "student_id": student, "to_group": target},
        headers=ten["headers"],
    )
    assert resp.status_code == 422  # 5 -> 6 without confirmation
    detail = resp.json()["detail"]
    assert "size" in detail or "max" in detail

    resp = client.post(
        f"/api/cycles/{cid}/edits",
        json={"action": "move", "student_id": student, "to_group": target,
              "allow_oversize": True},
        headers=ten["headers"],
    )
    assert resp.status_code == 200, resp.text
    proposal = resp.json()
    sizes = sorted(len(g["members"]) for g in proposal["groups"])
    assert sizes == [4, 6]


def test_invalid_edit_leaves_proposal_unchanged(client, ten):
    cid = ten["cycle"]["id"]
    student = ten["proposal"]["groups"][0]["members"][0]
    target = ten["proposal"]["groups"][1]["group_id"]
    client.post(
        f"/api/cycles/{cid}/edits",
        json={"action": "move", "student_id": student, "to_group": target},
        headers=ten["headers"],
    )
    fetched = client.get(f"/api/cycles/{cid}/proposal", headers=ten["headers"]).json()
    assert fetched == ten["proposal"]


def test_edit_bumps_rev_and_invalidates_review_stamp(client, ten):
    cid = ten["cycle"]["id"]
    client.get(f"/api/cycles/{cid}/review-board", headers=ten["headers"])
    student = ten["proposal"]["groups"][0]["members"][0]
    target = ten["proposal"]["groups"][1]["group_id"]
    client.post(
        f"/api/cycles/{cid}/edits",
        json={"action": "move", "student_id": student, "to_group": target,
              "allow_oversize": True},
        headers=ten["headers"],
    )
    cycle = client.get(f"/api/cycles/{cid}", headers=ten["headers"]).json()
    assert cycle["proposal_rev"] == 2
    assert cycle["reviewed_rev"] == 1  # stale: must re-view before approving


def test_assign_unknown_student_404(client, ten):
    resp = client.post(
        f"/api/cycles/{ten['cycle']['id']}/edits",
        json={"action": "assign", "student_id": "ghost", "to_group": 1},
        headers=ten["headers"],
    )
    assert resp.status_code in (404, 422)


def test_assign_without_overlap_relays_constraint(client):
    headers = register_and_login(client)
    cls = make_class(
        client, headers,
        roster=[{"student_id": f"s{i:02d}", "name": f"S{i}"} for i in range(1, 5)],
    )
    cycle = make_cycle(client, headers, cls["id"],
                       config={"grid": SMALL_GRID, "min_overlap": 1})
    for sid, slots in {"s01": [1, 1, 0, 0], "s02": [1, 1, 0, 0],
                       "s03": [1, 1, 0, 0], "s04": [0, 0, 0, 1]}.items():
        s = join(client, cls, sid)
        client.put("/api/me/availability", json={"slots": slots}, headers=s)
    proposal = client.post(f"/api/cycles/{cycle['id']}/match", headers=headers).json()
    assert [u["student_id"] for u in proposal["unplaced"]] == ["s04"]

    resp = client.post(
        f"/api/cycles/{cycle['id']}/edits",
        json={"action": "assign", "student_id": "s04",
              "to_group": proposal["groups"][0]["group_id"]},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "overlap" in resp.json()["detail"].lower()


# --- low-overlap override ---------------------------------------------------------

@pytest.fixture()
def split(client):
    """Eight students in two disjoint availability blocks -> two groups of four
    with no cross overlap; any cross move violates min_overlap only."""
    headers = register_and_login(client)
    cls = make_class(
        client, headers,
        roster=[{"student_id": f"s{i:02d}", "name": f"S{i}"} for i in range(1, 9)],
    )
    cycle = make_cycle(client, headers, cls["id"],
                       config={"grid": SMALL_GRID, "min_overlap": 1})
    for i in range(1, 9):
        s = join(client, cls, f"s{i:02d}")
        slots = [1, 1, 0, 0] if i <= 4 else [0, 0, 1, 1]
        client.put("/api/me/availability", json={"slots": slots}, headers=s)
    proposal = client.post(f"/api/cycles/{cycle['id']}/match", headers=headers).json()
    assert sorted(len(g["members"]) for g in proposal["groups"]) == [4, 4]
    return {"headers": headers, "cls": cls, "cycle": cycle, "proposal": proposal}


def cross_move(split):
    """s from group A -> group B: source stays at min_size, zero shared slots."""
    groups = split["proposal"]["groups"]
    return {"action": "move", "student_id": groups[0]["members"][0],
            "to_group": groups[1]["group_id"]}


def test_low_overlap_edit_rejected_without_flag(client, split):
    resp = client.post(f"/api/cycles/{split['cycle']['id']}/edits",
                       json=cross_move(split), headers=split["headers"])
    assert resp.status_code == 422
    assert "min_overlap" in resp.json()["detail"]
    assert "allow_low_overlap" in resp.json()["detail"]


def test_low_overlap_edit_applies_with_flag(client, split):
    move = cross_move(split)
    resp = client.post(f"/api/cycles/{split['cycle']['id']}/edits",
                       json={**move, "allow_low_overlap": True},
                       headers=split["headers"])
    assert resp.status_code == 200, resp.text
    target = next(g for g in resp.json()["groups"] if g["group_id"] == move["to_group"])
    assert move["student_id"] in target["members"]
    assert target["meeting_slots"] == []  # surfaced, never invented
