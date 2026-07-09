"""Instructor forgot-password flow: anti-enumeration request, hashed
single-use tokens, log-based pilot delivery, full reset round-trip."""

import logging
import re

import pytest

pytest.importorskip("fastapi")

from test_auth import register_and_login


def request_reset(client, email):
    return client.post("/api/instructor/forgot-password", json={"email": email})


def extract_token(caplog):
    for record in caplog.records:
        m = re.search(r"token=([A-Za-z0-9_-]+)", record.getMessage())
        if m:
            return m.group(1)
    raise AssertionError("no reset link in the log")


def test_unknown_email_gets_200_and_no_rows(client, caplog):
    with caplog.at_level(logging.INFO):
        resp = request_reset(client, "nobody@x.org")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    db = client.app.state.db
    assert db.execute("SELECT COUNT(*) FROM password_resets").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM email_outbox").fetchone()[0] == 0


def test_known_email_creates_hashed_reset_and_outbox_row(client, caplog):
    register_and_login(client)
    with caplog.at_level(logging.INFO):
        resp = request_reset(client, "prof@x.org")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}  # indistinguishable from the unknown case

    token = extract_token(caplog)
    db = client.app.state.db
    reset = db.execute("SELECT * FROM password_resets").fetchone()
    assert reset["token_hash"] != token  # raw token never stored
    assert len(reset["token_hash"]) == 64  # sha256 hex

    outbox = db.execute("SELECT * FROM email_outbox").fetchone()
    assert outbox["kind"] == "password-reset"
    assert outbox["status"] == "disabled"
    assert outbox["recipient_email"] == "prof@x.org"
    assert "/reset-password?token=" in outbox["body"]


def test_full_reset_roundtrip(client, caplog):
    old_headers = register_and_login(client)
    with caplog.at_level(logging.INFO):
        request_reset(client, "prof@x.org")
    token = extract_token(caplog)

    resp = client.post("/api/instructor/reset-password",
                       json={"token": token, "password": "newpass9"})
    assert resp.status_code == 200

    # new password works, old one doesn't
    assert client.post("/api/instructor/login",
                       json={"email": "prof@x.org", "password": "newpass9"}
                       ).status_code == 200
    assert client.post("/api/instructor/login",
                       json={"email": "prof@x.org", "password": "hunter22"}
                       ).status_code == 401
    # pre-reset bearer tokens are revoked
    assert client.get("/api/instructor/me", headers=old_headers).status_code == 401
    # token is single-use
    resp = client.post("/api/instructor/reset-password",
                       json={"token": token, "password": "another9"})
    assert resp.status_code == 400


def test_expired_token_rejected(client, caplog):
    register_and_login(client)
    with caplog.at_level(logging.INFO):
        request_reset(client, "prof@x.org")
    token = extract_token(caplog)
    db = client.app.state.db
    db.execute("UPDATE password_resets SET expires_at = datetime('now', '-1 minute')")
    db.commit()
    resp = client.post("/api/instructor/reset-password",
                       json={"token": token, "password": "newpass9"})
    assert resp.status_code == 400


def test_garbage_token_rejected_uniformly(client):
    resp = client.post("/api/instructor/reset-password",
                       json={"token": "garbage", "password": "newpass9"})
    assert resp.status_code == 400
    assert "invalid or expired" in resp.json()["detail"]


def test_short_password_rejected(client, caplog):
    register_and_login(client)
    with caplog.at_level(logging.INFO):
        request_reset(client, "prof@x.org")
    token = extract_token(caplog)
    resp = client.post("/api/instructor/reset-password",
                       json={"token": token, "password": "short"})
    assert resp.status_code == 422
