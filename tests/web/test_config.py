"""Port resolution for deployment platforms (Railway/Heroku inject PORT)."""

from reflectool_web.__main__ import resolve_port


def test_defaults_to_8000():
    assert resolve_port({}) == 8000


def test_platform_port_is_honored():
    assert resolve_port({"PORT": "9001"}) == 9001


def test_explicit_reflectool_port_wins_over_platform_port():
    assert resolve_port({"PORT": "9001", "REFLECTOOL_PORT": "7000"}) == 7000
