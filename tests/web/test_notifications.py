"""Student-facing notification endpoints: list + mark-all-read."""

import pytest

pytest.importorskip("fastapi")

from test_auth import make_class, register_and_login
from test_reassignments import first_move, published, reassign  # noqa: F401
from test_submissions import SMALL_GRID, join, make_cycle


def test_notifications_empty_before_any_reassignment(client, published):
    s01 = published["students"]["s01"]
    resp = client.get("/api/me/notifications", headers=s01)
    assert resp.status_code == 200
    assert resp.json() == {"notifications": [], "unread": 0}


def test_moved_student_sees_unread_notification(client, published):
    move = first_move(published)
    assert reassign(client, published, {**move, "confirm": True}).status_code == 200
    resp = client.get("/api/me/notifications",
                      headers=published["students"][move["student_id"]])
    assert resp.status_code == 200
    body = resp.json()
    assert body["unread"] == 1
    note = body["notifications"][0]
    assert note["kind"] == "group-changed"
    assert f"Group {move['to_group']}" in note["body"]
    assert note["read_at"] is None
    assert "gender" not in resp.text.lower()
    assert "disability" not in resp.text.lower()


def test_mark_read_zeroes_unread(client, published):
    move = first_move(published)
    reassign(client, published, {**move, "confirm": True})
    headers = published["students"][move["student_id"]]
    resp = client.post("/api/me/notifications/read", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["marked"] == 1
    after = client.get("/api/me/notifications", headers=headers).json()
    assert after["unread"] == 0
    assert after["notifications"][0]["read_at"] is not None


def test_unaffected_student_sees_nothing(client):
    """Three groups; a move between two of them must not notify the third."""
    headers = register_and_login(client)
    cls = make_class(
        client, headers,
        roster=[{"student_id": f"s{i:02d}", "name": f"S{i}"} for i in range(1, 13)],
    )
    cycle = make_cycle(client, headers, cls["id"],
                       config={"grid": SMALL_GRID, "min_overlap": 1})
    students = {}
    for i in range(1, 13):
        sid = f"s{i:02d}"
        students[sid] = join(client, cls, sid)
        client.put("/api/me/availability", json={"slots": [1, 1, 1, 1]},
                   headers=students[sid])
    proposal = client.post(f"/api/cycles/{cycle['id']}/match", headers=headers).json()
    assert len(proposal["groups"]) >= 3, proposal
    client.get(f"/api/cycles/{cycle['id']}/review-board", headers=headers)
    client.post(f"/api/cycles/{cycle['id']}/approve", headers=headers)
    client.post(f"/api/cycles/{cycle['id']}/publish", headers=headers)

    groups = proposal["groups"]
    donor = next(g for g in groups if len(g["members"]) > 3)
    receiver = next(g for g in groups
                    if g["group_id"] != donor["group_id"] and len(g["members"]) < 5)
    bystander_group = next(g for g in groups
                           if g["group_id"] not in (donor["group_id"], receiver["group_id"]))
    resp = client.post(
        f"/api/cycles/{cycle['id']}/reassignments",
        json={"action": "move", "student_id": donor["members"][0],
              "to_group": receiver["group_id"], "confirm": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    bystander = bystander_group["members"][0]
    resp = client.get("/api/me/notifications", headers=students[bystander])
    assert resp.json() == {"notifications": [], "unread": 0}


def test_notifications_require_student_token(client, published):
    resp = client.get("/api/me/notifications", headers=published["headers"])
    assert resp.status_code in (401, 403)
