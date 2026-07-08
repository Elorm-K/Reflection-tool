"""Static SPA serving: built frontend at /, API untouched, SPA fallback."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient


@pytest.fixture()
def static_client(tmp_path):
    from reflectool_web.app import create_app

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>GroupMatcher</title>")
    (dist / "assets" / "app.js").write_text("console.log('gm')")

    app = create_app(db_path=str(tmp_path / "t.db"), static_dir=str(dist))
    with TestClient(app) as c:
        yield c


def test_index_served_at_root(static_client):
    resp = static_client.get("/")
    assert resp.status_code == 200
    assert "GroupMatcher" in resp.text


def test_assets_served(static_client):
    assert static_client.get("/assets/app.js").status_code == 200


def test_spa_fallback_for_client_routes(static_client):
    resp = static_client.get("/i/classes/3/review")
    assert resp.status_code == 200
    assert "GroupMatcher" in resp.text


def test_api_routes_not_swallowed(static_client):
    assert static_client.get("/api/health").json() == {"status": "ok"}
    assert static_client.get("/api/nonexistent").status_code == 404


def test_app_without_static_dir_still_works(client):
    assert client.get("/api/health").status_code == 200
