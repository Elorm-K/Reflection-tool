"""FastAPI application factory for the Reflectool web layer."""

import os

from fastapi import FastAPI

from .db import connect
from .routers import instructor, student


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title="Reflectool")
    app.state.db = connect(db_path or os.environ.get("REFLECTOOL_DB", "state/reflectool.db"))

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(instructor.router)
    app.include_router(student.router)
    return app
