"""Lifecycle over HTTP: review-before-approve gate, approve -> publish,
student my-group visibility."""

import pytest

pytest.importorskip("fastapi")

from test_auth import make_class, register_and_login
from test_submissions import SMALL_GRID, join, make_cycle


@pytest.fixture()
def matched(client):
    headers = register_and_login(client)
    cls = make_class(
        client, headers,
        roster=[{"student_id": f"s{i:02d}", "name": f"Student {i}"} for i in range(1, 9)],
    )
    cycle = make_cycle(client, headers, cls["id"],
                       config={"grid": SMALL_GRID, "min_overlap": 1})
    for i in range(1, 9):
        s = join(client, cls, f"s{i:02d}")
        client.put("/api/me/availability", json={"slots": [1, 1, 1, 1]}, headers=s)
    proposal = client.post(f"/api/cycles/{cycle['id']}/match", headers=headers).json()
    return {"headers": headers, "cls": cls, "cycle": cycle, "proposal": proposal}


def review(client, m):
    assert client.get(f"/api/cycles/{m['cycle']['id']}/review-board",
                      headers=m["headers"]).status_code == 200


def approve(client, m):
    return client.post(f"/api/cycles/{m['cycle']['id']}/approve", headers=m["headers"])


def publish(client, m):
    return client.post(f"/api/cycles/{m['cycle']['id']}/publish", headers=m["headers"])


# --- the review-before-approve gate ------------------------------------------------

def test_approve_without_review_is_rejected(client, matched):
    resp = approve(client, matched)
    assert resp.status_code == 409
    assert "review" in resp.json()["detail"].lower()


def test_approve_after_review_succeeds(client, matched):
    review(client, matched)
    resp = approve(client, matched)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    cycle = client.get(f"/api/cycles/{matched['cycle']['id']}",
                       headers=matched["headers"]).json()
    assert cycle["status"] == "approved"


def test_edit_after_review_invalidates_gate(client, matched):
    review(client, matched)
    student = matched["proposal"]["groups"][0]["members"][0]
    target = matched["proposal"]["groups"][1]["group_id"]
    resp = client.post(
        f"/api/cycles/{matched['cycle']['id']}/edits",
        json={"action": "move", "student_id": student, "to_group": target},
        headers=matched["headers"],
    )
    assert resp.status_code == 200, resp.text  # 4+4 -> 3+5, a legal move
    assert approve(client, matched).status_code == 409  # stale review
    review(client, matched)
    assert approve(client, matched).status_code == 200


# --- linear transitions --------------------------------------------------------------

def test_publish_before_approve_rejected(client, matched):
    review(client, matched)
    resp = publish(client, matched)
    assert resp.status_code == 409


def test_publish_after_approve_notifies(client, matched):
    review(client, matched)
    approve(client, matched)
    resp = publish(client, matched)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "published"
    assert body["notified"] == 8


def test_double_approve_and_double_publish_rejected(client, matched):
    review(client, matched)
    approve(client, matched)
    assert approve(client, matched).status_code == 409
    publish(client, matched)
    assert publish(client, matched).status_code == 409


def test_edits_blocked_after_approve(client, matched):
    review(client, matched)
    approve(client, matched)
    student = matched["proposal"]["groups"][0]["members"][0]
    resp = client.post(
        f"/api/cycles/{matched['cycle']['id']}/edits",
        json={"action": "move", "student_id": student, "to_group": 2},
        headers=matched["headers"],
    )
    assert resp.status_code == 409


def test_rematch_blocked_after_approve(client, matched):
    review(client, matched)
    approve(client, matched)
    resp = client.post(f"/api/cycles/{matched['cycle']['id']}/match",
                       headers=matched["headers"])
    assert resp.status_code == 409


# --- student my-group -----------------------------------------------------------------

def test_my_group_hidden_until_published(client, matched):
    s = join(client, matched["cls"], "s01")
    resp = client.get("/api/me/group", headers=s)
    assert resp.status_code == 409
    assert "not published" in resp.json()["detail"].lower()
    review(client, matched)
    approve(client, matched)
    resp = client.get("/api/me/group", headers=s)  # approved but not published
    assert resp.status_code == 409


def test_my_group_after_publish(client, matched):
    review(client, matched)
    approve(client, matched)
    publish(client, matched)
    s = join(client, matched["cls"], "s01")
    resp = client.get("/api/me/group", headers=s)
    assert resp.status_code == 200
    body = resp.json()
    assert body["group_number"] >= 1
    assert "Student 1" in body["members"]
    assert body["meeting_slots"]
    assert "gender" not in resp.text and "disability" not in resp.text


def test_notifications_preview_for_instructor(client, matched):
    review(client, matched)
    approve(client, matched)
    publish(client, matched)
    resp = client.get(f"/api/cycles/{matched['cycle']['id']}/notifications",
                      headers=matched["headers"])
    assert resp.status_code == 200
    views = resp.json()
    assert len(views) == 8
    assert all("gender" not in str(v) for v in views.values())
