"""Group-chosen meeting time: member and instructor set/update, group
notification fan-out, overlay never touches the proposal."""

import pytest

pytest.importorskip("fastapi")

from test_reassignments import published  # noqa: F401


def group_of(p, sid):
    return next(g for g in p["proposal"]["groups"] if sid in g["members"])


# --- student set/update ---------------------------------------------------------

def test_member_sets_meeting_time_and_group_sees_it(client, published):
    resp = client.put("/api/me/group/meeting", json={"label": "Fridays 7pm, library"},
                      headers=published["students"]["s01"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["chosen_meeting"]["label"] == "Fridays 7pm, library"
    assert body["chosen_meeting"]["set_by"] == "Student 1"

    # every member of the group sees it on /me/group
    other = next(m for m in group_of(published, "s01")["members"] if m != "s01")
    mine = client.get("/api/me/group", headers=published["students"][other]).json()
    assert mine["chosen_meeting"]["label"] == "Fridays 7pm, library"
    # matcher-proposed slots are still there, untouched
    assert mine["meeting_slots"]


def test_other_members_notified_setter_is_not(client, published):
    client.put("/api/me/group/meeting", json={"label": "Wed 09:00"},
               headers=published["students"]["s01"])
    members = group_of(published, "s01")["members"]
    for sid in members:
        notes = client.get("/api/me/notifications",
                           headers=published["students"][sid]).json()
        if sid == "s01":
            assert notes["unread"] == 0
        else:
            assert notes["unread"] == 1
            assert notes["notifications"][0]["kind"] == "meeting-updated"
            assert "Wed 09:00" in notes["notifications"][0]["body"]
    # students outside the group hear nothing
    outsider = next(s for s in published["students"] if s not in members)
    notes = client.get("/api/me/notifications",
                       headers=published["students"][outsider]).json()
    assert notes["unread"] == 0


def test_update_overwrites_and_renotifies(client, published):
    headers = published["students"]["s01"]
    client.put("/api/me/group/meeting", json={"label": "Wed 09:00"}, headers=headers)
    client.put("/api/me/group/meeting", json={"label": "Thu 10:00"}, headers=headers)
    mine = client.get("/api/me/group", headers=headers).json()
    assert mine["chosen_meeting"]["label"] == "Thu 10:00"
    other = next(m for m in group_of(published, "s01")["members"] if m != "s01")
    notes = client.get("/api/me/notifications",
                       headers=published["students"][other]).json()
    assert notes["unread"] == 2


def test_meeting_label_validated(client, published):
    headers = published["students"]["s01"]
    assert client.put("/api/me/group/meeting", json={"label": "   "},
                      headers=headers).status_code == 422
    assert client.put("/api/me/group/meeting", json={"label": "x" * 200},
                      headers=headers).status_code == 422


def test_meeting_blocked_before_publish(client):
    from test_auth import make_class, register_and_login
    from test_submissions import SMALL_GRID, join, make_cycle

    headers = register_and_login(client)
    cls = make_class(client, headers,
                     roster=[{"student_id": "s01", "name": "Ada"}])
    make_cycle(client, headers, cls["id"],
               config={"grid": SMALL_GRID, "min_overlap": 1})
    s = join(client, cls, "s01")
    resp = client.put("/api/me/group/meeting", json={"label": "Wed 09:00"}, headers=s)
    assert resp.status_code == 409


def test_proposal_not_mutated_by_chosen_meeting(client, published):
    before = client.get(f"/api/cycles/{published['cycle']['id']}/proposal",
                        headers=published["headers"]).json()
    client.put("/api/me/group/meeting", json={"label": "Sat 11:00"},
               headers=published["students"]["s01"])
    after = client.get(f"/api/cycles/{published['cycle']['id']}/proposal",
                       headers=published["headers"]).json()
    assert before == after  # overlay only — determinism untouched


# --- instructor set ----------------------------------------------------------------

def test_instructor_sets_meeting_and_all_members_notified(client, published):
    gid = group_of(published, "s01")["group_id"]
    resp = client.put(
        f"/api/cycles/{published['cycle']['id']}/groups/{gid}/meeting",
        json={"label": "Mon 08:00, room 12"}, headers=published["headers"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["chosen_meeting"]["set_by"] == "instructor"

    for sid in group_of(published, "s01")["members"]:
        notes = client.get("/api/me/notifications",
                           headers=published["students"][sid]).json()
        assert notes["unread"] == 1
        assert "Mon 08:00, room 12" in notes["notifications"][0]["body"]

    audit = client.get(f"/api/cycles/{published['cycle']['id']}/audit",
                       headers=published["headers"]).json()["entries"]
    assert any(e["action"] == "meeting-set" for e in audit)


def test_instructor_meeting_requires_published_and_known_group(client, published):
    resp = client.put(
        f"/api/cycles/{published['cycle']['id']}/groups/999/meeting",
        json={"label": "Mon 08:00"}, headers=published["headers"])
    assert resp.status_code == 404


def test_review_board_carries_meetings(client, published):
    client.put("/api/me/group/meeting", json={"label": "Fri 19:00"},
               headers=published["students"]["s01"])
    gid = group_of(published, "s01")["group_id"]
    board = client.get(f"/api/cycles/{published['cycle']['id']}/review-board",
                       headers=published["headers"]).json()
    assert board["meetings"][str(gid)]["label"] == "Fri 19:00"
