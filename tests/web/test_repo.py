"""Repo-layer tests: schema constraints and data access, no HTTP."""

import sqlite3

import pytest

pytest.importorskip("fastapi")

from reflectool_web import repo
from reflectool_web.db import connect


@pytest.fixture()
def db(tmp_path):
    conn = connect(str(tmp_path / "repo.db"))
    yield conn
    conn.close()


def test_connect_is_idempotent_and_enforces_foreign_keys(tmp_path):
    path = str(tmp_path / "x.db")
    c1 = connect(path)
    c1.close()
    c2 = connect(path)  # re-running schema on an existing db must not fail
    with pytest.raises(sqlite3.IntegrityError):
        c2.execute(
            "INSERT INTO classes (instructor_id, name, class_code) VALUES (999, 'x', 'ABC123')"
        )
    c2.close()


def test_create_class_generates_unique_code(db):
    iid = repo.create_instructor(db, "a@x.org", "hash", "Prof A")
    c1 = repo.create_class(db, iid, name="CS50", term="Fall 2026")
    c2 = repo.create_class(db, iid, name="CS101", term="Fall 2026")
    assert c1["class_code"] != c2["class_code"]
    assert len(c1["class_code"]) == 6
    assert repo.get_class_by_code(db, c1["class_code"])["id"] == c1["id"]


def test_duplicate_instructor_email_rejected(db):
    repo.create_instructor(db, "a@x.org", "h", "A")
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_instructor(db, "a@x.org", "h2", "B")


def test_roster_upload_replaces_and_enforces_unique_student_ids(db):
    iid = repo.create_instructor(db, "a@x.org", "h", "A")
    cls = repo.create_class(db, iid, name="CS50", term="F26")
    repo.replace_roster(db, cls["id"], [("2024-001", "Jane Doe"), ("2024-002", "Mark S")])
    repo.replace_roster(db, cls["id"], [("2024-001", "Jane Doe")])
    assert len(repo.list_roster(db, cls["id"])) == 1
    with pytest.raises(ValueError):
        repo.replace_roster(db, cls["id"], [("2024-001", "A"), ("2024-001", "B")])


def test_enrollment_claim_is_first_wins(db):
    iid = repo.create_instructor(db, "a@x.org", "h", "A")
    cls = repo.create_class(db, iid, name="CS50", term="F26")
    repo.replace_roster(db, cls["id"], [("2024-001", "Jane Doe")])
    e1 = repo.claim_enrollment(db, cls["id"], "2024-001")
    e2 = repo.claim_enrollment(db, cls["id"], "2024-001")  # re-join: same enrollment
    assert e1["id"] == e2["id"]
    assert repo.claim_enrollment(db, cls["id"], "2024-999") is None  # not on roster


def test_cycle_and_submission_upsert(db):
    iid = repo.create_instructor(db, "a@x.org", "h", "A")
    cls = repo.create_class(db, iid, name="CS50", term="F26")
    repo.replace_roster(db, cls["id"], [("2024-001", "Jane Doe")])
    enr = repo.claim_enrollment(db, cls["id"], "2024-001")
    cyc = repo.create_cycle(db, cls["id"], label="Week 1", config={"min_overlap": 2})
    assert cyc["status"] == "collecting"

    repo.upsert_availability(db, cyc["id"], enr["id"], [True, False, True])
    repo.upsert_availability(db, cyc["id"], enr["id"], [False, False, True])
    subs = repo.list_submissions(db, cyc["id"])
    assert len(subs) == 1
    assert subs[0]["availability"] == [False, False, True]

    repo.upsert_survey(db, cyc["id"], enr["id"], gender="woman", disability="adhd")
    subs = repo.list_submissions(db, cyc["id"])
    assert subs[0]["gender"] == "woman"
    # survey update must not clobber availability
    assert subs[0]["availability"] == [False, False, True]


def test_tokens_roundtrip(db):
    iid = repo.create_instructor(db, "a@x.org", "h", "A")
    tok = repo.issue_token(db, kind="instructor", instructor_id=iid)
    found = repo.lookup_token(db, tok)
    assert found["kind"] == "instructor" and found["instructor_id"] == iid
    assert repo.lookup_token(db, "nonsense") is None


def test_messages_append_and_list_since(db):
    iid = repo.create_instructor(db, "a@x.org", "h", "A")
    cls = repo.create_class(db, iid, name="CS50", term="F26")
    repo.replace_roster(db, cls["id"], [("2024-001", "Jane")])
    enr = repo.claim_enrollment(db, cls["id"], "2024-001")
    cyc = repo.create_cycle(db, cls["id"], label="W1", config={})
    m1 = repo.add_message(db, cyc["id"], group_id=1, enrollment_id=enr["id"], body="hi")
    m2 = repo.add_message(db, cyc["id"], group_id=1, enrollment_id=enr["id"], body="yo")
    assert [m["body"] for m in repo.list_messages(db, cyc["id"], 1)] == ["hi", "yo"]
    assert [m["id"] for m in repo.list_messages(db, cyc["id"], 1, since=m1["id"])] == [m2["id"]]
    assert repo.list_messages(db, cyc["id"], 2) == []


def test_audit_log(db):
    iid = repo.create_instructor(db, "a@x.org", "h", "A")
    cls = repo.create_class(db, iid, name="CS50", term="F26")
    cyc = repo.create_cycle(db, cls["id"], label="W1", config={})
    repo.add_audit(db, cyc["id"], actor="instructor", action="match", detail="proposal generated")
    entries = repo.list_audit(db, cyc["id"])
    assert entries[0]["action"] == "match"
