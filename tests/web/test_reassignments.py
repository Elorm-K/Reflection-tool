"""Post-publish reassignment: server-enforced confirm, hard-constraint
re-validation, and notification fan-out to affected students."""

import pytest

pytest.importorskip("fastapi")

from test_auth import make_class, register_and_login
from test_submissions import SMALL_GRID, join, make_cycle


@pytest.fixture()
def published(client):
    """8 students, everyone available everywhere -> two groups of 4, published.
    Student tokens kept so we can check their /me surfaces afterwards."""
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
    client.post(f"/api/cycles/{cycle['id']}/match", headers=headers)
    assert client.get(f"/api/cycles/{cycle['id']}/review-board",
                      headers=headers).status_code == 200
    assert client.post(f"/api/cycles/{cycle['id']}/approve",
                       headers=headers).status_code == 200
    assert client.post(f"/api/cycles/{cycle['id']}/publish",
                       headers=headers).status_code == 200
    proposal = client.get(f"/api/cycles/{cycle['id']}/proposal", headers=headers).json()
    return {"headers": headers, "cls": cls, "cycle": cycle,
            "proposal": proposal, "students": students}


def reassign(client, p, body):
    return client.post(f"/api/cycles/{p['cycle']['id']}/reassignments",
                       json=body, headers=p["headers"])


def first_move(p):
    """A legal move: first member of group A into group B (4+4 -> 3+5)."""
    groups = p["proposal"]["groups"]
    return {"action": "move", "student_id": groups[0]["members"][0],
            "to_group": groups[1]["group_id"]}


# --- gates ---------------------------------------------------------------------

def test_reassignment_requires_explicit_confirm(client, published):
    resp = reassign(client, published, first_move(published))
    assert resp.status_code == 422
    assert "confirm" in resp.json()["detail"].lower()


def test_reassignment_blocked_before_publish(client):
    headers = register_and_login(client)
    cls = make_class(
        client, headers,
        roster=[{"student_id": f"s{i:02d}", "name": f"S{i}"} for i in range(1, 9)],
    )
    cycle = make_cycle(client, headers, cls["id"],
                       config={"grid": SMALL_GRID, "min_overlap": 1})
    for i in range(1, 9):
        s = join(client, cls, f"s{i:02d}")
        client.put("/api/me/availability", json={"slots": [1, 1, 1, 1]}, headers=s)
    proposal = client.post(f"/api/cycles/{cycle['id']}/match", headers=headers).json()
    student = proposal["groups"][0]["members"][0]
    resp = client.post(
        f"/api/cycles/{cycle['id']}/reassignments",
        json={"action": "move", "student_id": student,
              "to_group": proposal["groups"][1]["group_id"], "confirm": True},
        headers=headers,
    )
    assert resp.status_code == 409


def test_plain_edits_still_blocked_after_publish(client, published):
    resp = client.post(
        f"/api/cycles/{published['cycle']['id']}/edits",
        json=first_move(published),
        headers=published["headers"],
    )
    assert resp.status_code == 409


# --- the happy path --------------------------------------------------------------

def test_confirmed_move_applies_and_student_sees_new_group(client, published):
    move = first_move(published)
    resp = reassign(client, published, {**move, "confirm": True})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    target = next(g for g in body["proposal"]["groups"]
                  if g["group_id"] == move["to_group"])
    assert move["student_id"] in target["members"]
    assert body["notified"] >= 1

    mine = client.get("/api/me/group",
                      headers=published["students"][move["student_id"]])
    assert mine.status_code == 200
    assert mine.json()["group_number"] == move["to_group"]


def test_constraint_violation_relayed_and_proposal_unchanged(client, published):
    groups = published["proposal"]["groups"]
    # Two moves out of the same group of 4 -> the second leaves it at 2 (< min_size)
    first, second = groups[0]["members"][0], groups[0]["members"][1]
    to_group = groups[1]["group_id"]
    assert reassign(client, published,
                    {"action": "move", "student_id": first,
                     "to_group": to_group, "confirm": True}).status_code == 200
    resp = reassign(client, published,
                    {"action": "move", "student_id": second,
                     "to_group": to_group, "confirm": True})
    assert resp.status_code == 422
    assert "size" in resp.json()["detail"] or "min_overlap" in resp.json()["detail"]
    after = client.get(f"/api/cycles/{published['cycle']['id']}/proposal",
                       headers=published["headers"]).json()
    assert second in next(g for g in after["groups"]
                          if g["group_id"] == groups[0]["group_id"])["members"]


def test_unknown_student_404(client, published):
    resp = reassign(client, published,
                    {"action": "move", "student_id": "ghost", "to_group": 1,
                     "confirm": True})
    assert resp.status_code == 404


# --- notifications ---------------------------------------------------------------

def test_move_notifies_student_and_both_groups(client, published):
    move = first_move(published)
    groups = published["proposal"]["groups"]
    source_members = set(groups[0]["members"])
    target_members = set(groups[1]["members"])
    resp = reassign(client, published, {**move, "confirm": True})
    assert resp.status_code == 200
    # everyone in the two affected groups is notified, moved student included
    assert resp.json()["notified"] == len(source_members | target_members)

    db = client.app.state.db
    rows = db.execute(
        "SELECT n.kind, n.body, r.student_ext_id FROM notifications n"
        " JOIN enrollments e ON e.id = n.enrollment_id"
        " JOIN class_roster r ON r.id = e.roster_id"
    ).fetchall()
    by_student = {r["student_ext_id"]: r for r in rows}
    assert by_student[move["student_id"]]["kind"] == "group-changed"
    assert f"Group {move['to_group']}" in by_student[move["student_id"]]["body"]
    for sid in (source_members | target_members) - {move["student_id"]}:
        assert by_student[sid]["kind"] == "group-updated"
    # nobody outside the affected groups was notified
    assert set(by_student) == source_members | target_members
    # demographic-free bodies
    for r in rows:
        assert "gender" not in r["body"].lower()
        assert "disability" not in r["body"].lower()

    outbox = db.execute("SELECT status, sent_at FROM email_outbox").fetchall()
    assert len(outbox) == len(rows)
    assert all(o["status"] == "disabled" and o["sent_at"] is None for o in outbox)


def test_reassignment_audited(client, published):
    move = first_move(published)
    reassign(client, published, {**move, "confirm": True})
    audit = client.get(f"/api/cycles/{published['cycle']['id']}/audit",
                       headers=published["headers"]).json()["entries"]
    assert any(e["action"] == "reassign" for e in audit)


# --- assign an unplaced student post-publish ---------------------------------------

def test_assign_unplaced_after_publish(client):
    """min_size=max_size=5 with 6 students leaves exactly one unplaced; the
    instructor can place them post-publish with the oversize override."""
    headers = register_and_login(client)
    cls = make_class(
        client, headers,
        roster=[{"student_id": f"s{i:02d}", "name": f"S{i}"} for i in range(1, 7)],
    )
    cycle = make_cycle(client, headers, cls["id"],
                       config={"grid": SMALL_GRID, "min_overlap": 1,
                               "min_size": 5, "max_size": 5})
    students = {}
    for i in range(1, 7):
        sid = f"s{i:02d}"
        students[sid] = join(client, cls, sid)
        client.put("/api/me/availability", json={"slots": [1, 1, 1, 1]},
                   headers=students[sid])
    proposal = client.post(f"/api/cycles/{cycle['id']}/match", headers=headers).json()
    assert len(proposal["unplaced"]) == 1, proposal
    unplaced_sid = proposal["unplaced"][0]["student_id"]
    group_id = proposal["groups"][0]["group_id"]

    assert client.get(f"/api/cycles/{cycle['id']}/review-board",
                      headers=headers).status_code == 200
    client.post(f"/api/cycles/{cycle['id']}/approve", headers=headers)
    client.post(f"/api/cycles/{cycle['id']}/publish", headers=headers)

    resp = client.post(
        f"/api/cycles/{cycle['id']}/reassignments",
        json={"action": "assign", "student_id": unplaced_sid, "to_group": group_id,
              "allow_oversize": True, "confirm": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    mine = client.get("/api/me/group", headers=students[unplaced_sid])
    assert mine.status_code == 200
    assert mine.json()["group_number"] == group_id
    db = client.app.state.db
    kinds = [r["kind"] for r in db.execute(
        "SELECT n.kind FROM notifications n JOIN enrollments e ON e.id = n.enrollment_id"
        " JOIN class_roster r ON r.id = e.roster_id WHERE r.student_ext_id = ?",
        (unplaced_sid,),
    ).fetchall()]
    assert "group-changed" in kinds


# --- low-overlap override ---------------------------------------------------------

@pytest.fixture()
def published_split(client):
    """Like `published`, but two disjoint availability blocks (4 early, 4 late):
    any cross move violates min_overlap only. Published, student tokens kept."""
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
        slots = [1, 1, 0, 0] if i <= 4 else [0, 0, 1, 1]
        client.put("/api/me/availability", json={"slots": slots},
                   headers=students[sid])
    client.post(f"/api/cycles/{cycle['id']}/match", headers=headers)
    assert client.get(f"/api/cycles/{cycle['id']}/review-board",
                      headers=headers).status_code == 200
    assert client.post(f"/api/cycles/{cycle['id']}/approve",
                       headers=headers).status_code == 200
    assert client.post(f"/api/cycles/{cycle['id']}/publish",
                       headers=headers).status_code == 200
    proposal = client.get(f"/api/cycles/{cycle['id']}/proposal", headers=headers).json()
    return {"headers": headers, "cls": cls, "cycle": cycle,
            "proposal": proposal, "students": students}


def test_live_low_overlap_rejected_without_flag(client, published_split):
    move = first_move(published_split)
    resp = reassign(client, published_split, {**move, "confirm": True})
    assert resp.status_code == 422
    assert "min_overlap" in resp.json()["detail"]


def test_live_low_overlap_applies_with_flag_and_safe_notification(client, published_split):
    move = first_move(published_split)
    resp = reassign(client, published_split,
                    {**move, "confirm": True, "allow_low_overlap": True})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    target = next(g for g in body["proposal"]["groups"]
                  if g["group_id"] == move["to_group"])
    assert move["student_id"] in target["members"]
    assert target["meeting_slots"] == []
    assert body["notified"] >= 1

    # the moved student's notification says there's no shared time yet —
    # never an empty "New meeting time: ." and never demographics
    notes = client.get("/api/me/notifications",
                       headers=published_split["students"][move["student_id"]]).json()
    note = notes["notifications"][0]
    assert note["kind"] == "group-changed"
    assert "does not yet have a shared meeting time" in note["body"]
    assert "New meeting time: ." not in note["body"]
    assert "gender" not in note["body"].lower()
    assert "disability" not in note["body"].lower()
