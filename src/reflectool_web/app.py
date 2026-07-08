"""FastAPI application factory for the Reflectool web layer."""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import connect
from .routers import cycles, instructor, student


def create_app(db_path: str | None = None, static_dir: str | None = None) -> FastAPI:
    app = FastAPI(title="Reflectool")
    app.state.db = connect(db_path or os.environ.get("REFLECTOOL_DB", "state/reflectool.db"))

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(instructor.router)
    app.include_router(student.router)
    app.include_router(cycles.router)

    static_dir = static_dir or os.environ.get("REFLECTOOL_STATIC")
    if static_dir and Path(static_dir, "index.html").is_file():
        index = Path(static_dir, "index.html")
        assets = Path(static_dir, "assets")
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            # API 404s must stay JSON; everything else falls back to the SPA.
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="not found")
            candidate = Path(static_dir) / full_path
            if full_path and candidate.is_file() and candidate.resolve().is_relative_to(
                Path(static_dir).resolve()
            ):
                return FileResponse(candidate)
            return FileResponse(index)

    return app
