"""Group chat: membership scoping, publication gating, polling cursor,
instructor visibility. Plus export.csv, explain, audit, reset-claim."""

import pytest

pytest.importorskip("fastapi")

from test_auth import make_class, register_and_login
from test_submissions import SMALL_GRID, join, make_cycle


@pytest.fixture()
def published(client):
    headers = register_and_login(client)
    cls = make_class(
        client, headers,
        roster=[{"student_id": f"s{i:02d}", "name": f"Student {i}"} for i in range(1, 9)],
    )
    cycle = make_cycle(client, headers, cls["id"],
                       config={"grid": SMALL_GRID, "min_overlap": 1})
    students = {}
    for i in range(1, 9):
        sid = f"s{i:02d}"
        students[sid] = join(client, cls, sid)
        client.put("/api/me/availability", json={"slots": [1, 1, 1, 1]},
                   headers=students[sid])
    cid = cycle["id"]
    proposal = client.post(f"/api/cycles/{cid}/match", headers=headers).json()
    client.get(f"/api/cycles/{cid}/review-board", headers=headers)
    client.post(f"/api/cycles/{cid}/approve", headers=headers)
    client.post(f"/api/cycles/{cid}/publish", headers=headers)
    groups = {g["group_id"]: g["members"] for g in proposal["groups"]}
    return {"headers": headers, "cls": cls, "cycle": cycle,
            "students": students, "groups": groups}


def _mates(published):
    """(same-group pair, member of the other group)"""
    gids = sorted(published["groups"])
    a, b = published["groups"][gids[0]][:2]
    other = published["groups"][gids[1]][0]
    return a, b, other


# --- chat -------------------------------------------------------------------------

def test_chat_blocked_before_publication(client):
    headers = register_and_login(client)
    cls = make_class(client, headers, roster=[{"student_id": "s01", "name": "A"}])
    make_cycle(client, headers, cls["id"])
    s = join(client, cls, "s01")
    assert client.get("/api/me/group/messages", headers=s).status_code == 409
    assert client.post("/api/me/group/messages", json={"body": "hi"},
                       headers=s).status_code == 409


def test_groupmates_share_a_thread_others_do_not(client, published):
    a, b, other = _mates(published)
    sa, sb, so = (published["students"][x] for x in (a, b, other))

    resp = client.post("/api/me/group/messages", json={"body": "hello group"}, headers=sa)
    assert resp.status_code == 201, resp.text

    seen_by_mate = client.get("/api/me/group/messages", headers=sb).json()["messages"]
    assert [m["body"] for m in seen_by_mate] == ["hello group"]
    assert seen_by_mate[0]["sender_name"] == "Student " + a[-1].lstrip("0")

    seen_by_other = client.get("/api/me/group/messages", headers=so).json()["messages"]
    assert seen_by_other == []


def test_chat_since_cursor(client, published):
    a, b, _ = _mates(published)
    sa, sb = published["students"][a], published["students"][b]
    first = client.post("/api/me/group/messages", json={"body": "one"},
                        headers=sa).json()
    client.post("/api/me/group/messages", json={"body": "two"}, headers=sb)
    resp = client.get(f"/api/me/group/messages?since={first['id']}", headers=sa).json()
    assert [m["body"] for m in resp["messages"]] == ["two"]


def test_chat_messages_are_student_safe(client, published):
    a, _, _ = _mates(published)
    sa = published["students"][a]
    client.post("/api/me/group/messages", json={"body": "checking"}, headers=sa)
    resp = client.get("/api/me/group/messages", headers=sa)
    assert "gender" not in resp.text and "disability" not in resp.text


def test_instructor_can_read_group_chat(client, published):
    a, _, _ = _mates(published)
    sa = published["students"][a]
    client.post("/api/me/group/messages", json={"body": "visible to instructor"},
                headers=sa)
    gid = next(g for g, members in published["groups"].items() if a in members)
    resp = client.get(
        f"/api/cycles/{published['cycle']['id']}/groups/{gid}/messages",
        headers=published["headers"],
    )
    assert resp.status_code == 200
    assert [m["body"] for m in resp.json()["messages"]] == ["visible to instructor"]


# --- export -----------------------------------------------------------------------

def test_export_csv_contains_groups_and_no_demographics(client, published):
    resp = client.get(f"/api/cycles/{published['cycle']['id']}/export.csv",
                      headers=published["headers"])
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    text = resp.text
    assert text.splitlines()[0] == "group_id,student_id,name,meeting_slots"
    assert "s01" in text
    assert "gender" not in text and "disability" not in text


# --- explain ----------------------------------------------------------------------

def test_explain_placed_student(client, published):
    a, _, _ = _mates(published)
    resp = client.get(
        f"/api/cycles/{published['cycle']['id']}/explain/{a}",
        headers=published["headers"],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["student_id"] == a
    assert body["group_size"] >= 3
    assert body["shared_slot_count"] >= 1
    assert "gender" not in resp.text


def test_explain_unknown_student_404(client, published):
    resp = client.get(
        f"/api/cycles/{published['cycle']['id']}/explain/ghost",
        headers=published["headers"],
    )
    assert resp.status_code == 404


# --- audit & reset-claim -------------------------------------------------------------

def test_audit_trail_lists_lifecycle_events(client, published):
    resp = client.get(f"/api/cycles/{published['cycle']['id']}/audit",
                      headers=published["headers"])
    assert resp.status_code == 200
    actions = [e["action"] for e in resp.json()["entries"]]
    for expected in ("match", "review-board-viewed", "approve", "publish"):
        assert expected in actions


def test_reset_claim_allows_rejoin(client, published):
    cls = published["cls"]
    resp = client.post(
        f"/api/classes/{cls['id']}/reset-claim",
        json={"student_id": "s01"},
        headers=published["headers"],
    )
    assert resp.status_code == 200
    rejoined = client.post(
        "/api/join", json={"class_code": cls["class_code"], "student_id": "s01"}
    )
    assert rejoined.status_code == 200
