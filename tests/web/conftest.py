"""Fixtures for the web-layer test suite.

The core matcher suite must stay runnable in a stdlib-only environment,
so everything here degrades to skips when FastAPI isn't installed.
"""

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    from reflectool_web.app import create_app

    app = create_app(db_path=str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c
