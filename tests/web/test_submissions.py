"""Cycles, availability/survey submissions, roster-status aggregates."""

import pytest

pytest.importorskip("fastapi")

from test_auth import make_class, register_and_login

SMALL_GRID = {"days": 1, "start": "08:00", "end": "10:00", "slot_minutes": 30}  # 4 slots


def make_cycle(client, headers, class_id, config=None, label="Week 1"):
    resp = client.post(
        f"/api/classes/{class_id}/cycles",
        json={"label": label, "config": config or {"grid": SMALL_GRID, "min_overlap": 1}},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def join(client, cls, student_id):
    resp = client.post(
        "/api/join", json={"class_code": cls["class_code"], "student_id": student_id}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


@pytest.fixture()
def setup(client):
    headers = register_and_login(client)
    cls = make_class(
        client, headers,
        roster=[{"student_id": "s01", "name": "Ada"}, {"student_id": "s02", "name": "Bo"}],
    )
    cycle = make_cycle(client, headers, cls["id"])
    return {"headers": headers, "cls": cls, "cycle": cycle}


# --- cycles -------------------------------------------------------------------

def test_create_cycle_validates_and_reports_grid(setup):
    cycle = setup["cycle"]
    assert cycle["status"] == "collecting"
    assert cycle["config"]["grid"]["num_slots"] == 4
    assert cycle["config"]["min_overlap"] == 1


def test_cycle_config_grid_locks_after_first_submission(client, setup):
    s = join(client, setup["cls"], "s01")
    assert client.put(
        "/api/me/availability", json={"slots": [1, 1, 0, 0]}, headers=s
    ).status_code == 200
    resp = client.patch(
        f"/api/cycles/{setup['cycle']['id']}/config",
        json={"grid": {"days": 7}},
        headers=setup["headers"],
    )
    assert resp.status_code == 409
    # non-grid config changes remain allowed
    resp = client.patch(
        f"/api/cycles/{setup['cycle']['id']}/config",
        json={"min_overlap": 2},
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["config"]["min_overlap"] == 2


# --- student /me and grid ------------------------------------------------------

def test_me_exposes_grid_and_submission_flags(client, setup):
    s = join(client, setup["cls"], "s01")
    me = client.get("/api/me", headers=s).json()
    assert me["cycle"]["grid"] == {**SMALL_GRID, "num_slots": 4}
    assert me["availability_submitted"] is False
    client.put("/api/me/availability", json={"slots": [1, 0, 1, 0]}, headers=s)
    client.put("/api/me/survey", json={"skip": True}, headers=s)
    me = client.get("/api/me", headers=s).json()
    assert me["availability_submitted"] is True
    assert me["survey_submitted"] is True


# --- availability ---------------------------------------------------------------

def test_availability_wrong_length_rejected(client, setup):
    s = join(client, setup["cls"], "s01")
    resp = client.put("/api/me/availability", json={"slots": [1, 0]}, headers=s)
    assert resp.status_code == 422
    assert "length 4" in resp.json()["detail"]


def test_availability_resubmission_overwrites(client, setup):
    s = join(client, setup["cls"], "s01")
    client.put("/api/me/availability", json={"slots": [1, 1, 1, 1]}, headers=s)
    client.put("/api/me/availability", json={"slots": [0, 0, 0, 1]}, headers=s)
    me = client.get("/api/me", headers=s).json()
    assert me["availability_submitted"] is True


# --- survey ---------------------------------------------------------------------

def test_survey_stores_but_never_echoes(client, setup):
    s = join(client, setup["cls"], "s01")
    resp = client.put(
        "/api/me/survey", json={"gender": "woman", "disability": "ADHD"}, headers=s
    )
    assert resp.status_code == 200
    assert "gender" not in resp.text and "woman" not in resp.text
    assert "disability" not in resp.text and "ADHD" not in resp.text
    me = client.get("/api/me", headers=s)
    assert me.json()["survey_submitted"] is True
    assert "woman" not in me.text


def test_survey_skip(client, setup):
    s = join(client, setup["cls"], "s01")
    assert client.put("/api/me/survey", json={"skip": True}, headers=s).status_code == 200
    assert client.get("/api/me", headers=s).json()["survey_submitted"] is True


# --- roster status (instructor intake view) --------------------------------------

def test_roster_status_aggregates(client, setup):
    headers = setup["headers"]
    s1 = join(client, setup["cls"], "s01")
    client.put("/api/me/availability", json={"slots": [1, 1, 0, 0]}, headers=s1)
    client.put("/api/me/survey", json={"gender": "woman", "disability": "none"}, headers=s1)

    resp = client.get(f"/api/cycles/{setup['cycle']['id']}/roster-status", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["roster_count"] == 2
    assert body["joined_count"] == 1
    assert body["submitted_count"] == 1
    assert body["missing"] == ["s02"]
    assert body["gender_counts"] == {"woman": 1}
    assert body["disability_counts"] == {"none": 1}
    assert body["min_free_slots"] == 2


def test_roster_status_requires_instructor(client, setup):
    s1 = join(client, setup["cls"], "s01")
    resp = client.get(f"/api/cycles/{setup['cycle']['id']}/roster-status", headers=s1)
    assert resp.status_code == 401
