"""Match endpoint: assembly from submissions, determinism, lifecycle effects."""

import pytest

pytest.importorskip("fastapi")

from test_auth import make_class, register_and_login
from test_submissions import SMALL_GRID, join, make_cycle


@pytest.fixture()
def matchable(client):
    """A class of six students who all submitted availability on the 4-slot grid."""
    headers = register_and_login(client)
    cls = make_class(
        client, headers,
        roster=[{"student_id": f"s{i:02d}", "name": f"Student {i}"} for i in range(1, 7)],
    )
    cycle = make_cycle(client, headers, cls["id"])
    availabilities = {
        "s01": [1, 1, 0, 0], "s02": [1, 1, 0, 0], "s03": [1, 1, 1, 0],
        "s04": [0, 0, 1, 1], "s05": [0, 0, 1, 1], "s06": [0, 1, 1, 1],
    }
    for sid, slots in availabilities.items():
        s = join(client, cls, sid)
        assert client.put(
            "/api/me/availability", json={"slots": slots}, headers=s
        ).status_code == 200
    return {"headers": headers, "cls": cls, "cycle": cycle}


def test_match_produces_proposal_and_updates_cycle(client, matchable):
    resp = client.post(f"/api/cycles/{matchable['cycle']['id']}/match",
                       headers=matchable["headers"])
    assert resp.status_code == 200, resp.text
    proposal = resp.json()
    assert proposal["status"] == "proposed"
    assert len(proposal["groups"]) == 2
    placed = sorted(sid for g in proposal["groups"] for sid in g["members"])
    assert placed == [f"s{i:02d}" for i in range(1, 7)]
    assert all(g["meeting_slots"] for g in proposal["groups"])

    cycle = client.get(f"/api/cycles/{matchable['cycle']['id']}",
                       headers=matchable["headers"]).json()
    assert cycle["status"] == "proposed"
    assert cycle["proposal_rev"] == 1


def test_match_is_deterministic(client, matchable):
    cid = matchable["cycle"]["id"]
    p1 = client.post(f"/api/cycles/{cid}/match", headers=matchable["headers"]).json()
    p2 = client.post(f"/api/cycles/{cid}/match", headers=matchable["headers"]).json()
    assert p1 == p2
    cycle = client.get(f"/api/cycles/{cid}", headers=matchable["headers"]).json()
    assert cycle["proposal_rev"] == 2  # re-match still bumps the revision


def test_match_with_no_submissions_rejected(client):
    headers = register_and_login(client)
    cls = make_class(client, headers, roster=[{"student_id": "s01", "name": "A"}])
    cycle = make_cycle(client, headers, cls["id"])
    resp = client.post(f"/api/cycles/{cycle['id']}/match", headers=headers)
    assert resp.status_code == 409
    assert "no availability submissions" in resp.json()["detail"]


def test_match_closes_submissions(client, matchable):
    client.post(f"/api/cycles/{matchable['cycle']['id']}/match",
                headers=matchable["headers"])
    s = join(client, matchable["cls"], "s01")
    resp = client.put("/api/me/availability", json={"slots": [1, 1, 1, 1]}, headers=s)
    assert resp.status_code == 409


def test_proposal_endpoint_returns_saved_proposal(client, matchable):
    cid = matchable["cycle"]["id"]
    assert client.get(f"/api/cycles/{cid}/proposal",
                      headers=matchable["headers"]).status_code == 404
    matched = client.post(f"/api/cycles/{cid}/match", headers=matchable["headers"]).json()
    fetched = client.get(f"/api/cycles/{cid}/proposal", headers=matchable["headers"]).json()
    assert fetched == matched
    assert "gender" not in str(fetched) and "disability" not in str(fetched)


def test_match_surfaces_unplaced_students(client):
    """A student with no overlap with anyone must appear in unplaced, never dropped."""
    headers = register_and_login(client)
    cls = make_class(
        client, headers,
        roster=[{"student_id": f"s{i:02d}", "name": f"S{i}"} for i in range(1, 5)],
    )
    cycle = make_cycle(client, headers, cls["id"])
    availabilities = {
        "s01": [1, 1, 0, 0], "s02": [1, 1, 0, 0], "s03": [1, 1, 0, 0],
        "s04": [0, 0, 0, 1],  # overlaps with nobody
    }
    for sid, slots in availabilities.items():
        s = join(client, cls, sid)
        client.put("/api/me/availability", json={"slots": slots}, headers=s)
    proposal = client.post(f"/api/cycles/{cycle['id']}/match", headers=headers).json()
    unplaced_ids = [u["student_id"] for u in proposal["unplaced"]]
    assert "s04" in unplaced_ids
    assert all(u["reason"] for u in proposal["unplaced"])
