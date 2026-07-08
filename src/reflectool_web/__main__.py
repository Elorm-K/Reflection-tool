"""`python -m reflectool_web` — run the pilot server with uvicorn."""

import os
from collections.abc import Mapping

import uvicorn

from .app import create_app


def resolve_port(env: Mapping[str, str] | None = None) -> int:
    """REFLECTOOL_PORT wins; else the platform-injected PORT (Railway, Heroku); else 8000."""
    if env is None:
        env = os.environ
    return int(env.get("REFLECTOOL_PORT") or env.get("PORT") or 8000)


if __name__ == "__main__":
    print(f"reflectool: db={os.environ.get('REFLECTOOL_DB', 'state/reflectool.db')}", flush=True)
    uvicorn.run(
        create_app(),
        host=os.environ.get("REFLECTOOL_HOST", "0.0.0.0"),
        port=resolve_port(),
        # single worker: cycle mutations rely on in-process locking
        workers=1,
    )
