"""Instructor auth, class CRUD, roster upload, student join — over HTTP."""

import pytest

pytest.importorskip("fastapi")


def register_and_login(client, email="prof@x.org", password="hunter22", name="Prof X"):
    resp = client.post(
        "/api/instructor/register",
        json={"email": email, "password": password, "name": name},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def make_class(client, headers, roster=None, name="CS50", term="Fall 2026"):
    resp = client.post("/api/classes", json={"name": name, "term": term}, headers=headers)
    assert resp.status_code == 201, resp.text
    cls = resp.json()
    if roster is not None:
        r = client.put(
            f"/api/classes/{cls['id']}/roster", json={"students": roster}, headers=headers
        )
        assert r.status_code == 200, r.text
    return cls


# --- instructor auth ---------------------------------------------------------

def test_register_login_and_me(client):
    headers = register_and_login(client)
    resp = client.post(
        "/api/instructor/login", json={"email": "prof@x.org", "password": "hunter22"}
    )
    assert resp.status_code == 200
    assert "token" in resp.json()
    me = client.get("/api/instructor/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "prof@x.org"


def test_login_wrong_password_rejected(client):
    register_and_login(client)
    resp = client.post(
        "/api/instructor/login", json={"email": "prof@x.org", "password": "wrong"}
    )
    assert resp.status_code == 401


def test_duplicate_registration_rejected(client):
    register_and_login(client)
    resp = client.post(
        "/api/instructor/register",
        json={"email": "prof@x.org", "password": "another-pass", "name": "Again"},
    )
    assert resp.status_code == 409


def test_instructor_routes_require_token(client):
    assert client.get("/api/classes").status_code == 401
    assert client.get(
        "/api/classes", headers={"Authorization": "Bearer bogus"}
    ).status_code == 401


# --- classes & ownership ------------------------------------------------------

def test_class_crud_and_ownership_isolation(client):
    h_a = register_and_login(client, email="a@x.org")
    h_b = register_and_login(client, email="b@x.org")
    cls = make_class(client, h_a)
    assert len(cls["class_code"]) == 6

    listed = client.get("/api/classes", headers=h_a).json()
    assert [c["id"] for c in listed] == [cls["id"]]
    assert client.get("/api/classes", headers=h_b).json() == []

    # instructor B cannot read or modify A's class
    assert client.get(f"/api/classes/{cls['id']}", headers=h_b).status_code == 404
    assert client.put(
        f"/api/classes/{cls['id']}/roster", json={"students": []}, headers=h_b
    ).status_code == 404


def test_roster_upload_and_listing(client):
    headers = register_and_login(client)
    cls = make_class(
        client, headers,
        roster=[{"student_id": "2024-001", "name": "Jane Doe"},
                {"student_id": "2024-002", "name": "Mark Smith"}],
    )
    resp = client.get(f"/api/classes/{cls['id']}/roster", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert [s["student_id"] for s in body["students"]] == ["2024-001", "2024-002"]
    assert all(s["joined"] is False for s in body["students"])


def test_roster_with_duplicate_ids_rejected(client):
    headers = register_and_login(client)
    cls = make_class(client, headers)
    resp = client.put(
        f"/api/classes/{cls['id']}/roster",
        json={"students": [{"student_id": "s1", "name": "A"},
                           {"student_id": "s1", "name": "B"}]},
        headers=headers,
    )
    assert resp.status_code == 422


# --- student join -------------------------------------------------------------

def test_student_join_happy_path(client):
    headers = register_and_login(client)
    cls = make_class(client, headers, roster=[{"student_id": "2024-001", "name": "Jane"}])
    resp = client.post(
        "/api/join", json={"class_code": cls["class_code"], "student_id": "2024-001"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "token" in body
    assert body["name"] == "Jane"
    assert body["class_name"] == "CS50"
    # roster now shows the claim
    roster = client.get(f"/api/classes/{cls['id']}/roster", headers=headers).json()
    assert roster["students"][0]["joined"] is True


def test_student_join_wrong_code_or_unknown_id(client):
    headers = register_and_login(client)
    cls = make_class(client, headers, roster=[{"student_id": "2024-001", "name": "Jane"}])
    assert client.post(
        "/api/join", json={"class_code": "ZZZZZZ", "student_id": "2024-001"}
    ).status_code == 404
    assert client.post(
        "/api/join", json={"class_code": cls["class_code"], "student_id": "nope"}
    ).status_code == 404


def test_student_rejoin_reissues_token(client):
    headers = register_and_login(client)
    cls = make_class(client, headers, roster=[{"student_id": "2024-001", "name": "Jane"}])
    t1 = client.post(
        "/api/join", json={"class_code": cls["class_code"], "student_id": "2024-001"}
    ).json()["token"]
    t2 = client.post(
        "/api/join", json={"class_code": cls["class_code"], "student_id": "2024-001"}
    ).json()["token"]
    assert t1 != t2
    # both tokens work (pilot: no invalidation on re-join)
    for t in (t1, t2):
        assert client.get(
            "/api/me", headers={"Authorization": f"Bearer {t}"}
        ).status_code == 200


def test_student_token_cannot_access_instructor_routes(client):
    headers = register_and_login(client)
    cls = make_class(client, headers, roster=[{"student_id": "2024-001", "name": "Jane"}])
    tok = client.post(
        "/api/join", json={"class_code": cls["class_code"], "student_id": "2024-001"}
    ).json()["token"]
    s_headers = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/classes", headers=s_headers).status_code == 401
    assert client.get(f"/api/classes/{cls['id']}/roster", headers=s_headers).status_code == 401
