"""`python -m reflectool_web` — run the pilot server with uvicorn."""

import os

import uvicorn

from .app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.environ.get("REFLECTOOL_HOST", "0.0.0.0"),
        port=int(os.environ.get("REFLECTOOL_PORT", "8000")),
        # single worker: cycle mutations rely on in-process locking
        workers=1,
    )
