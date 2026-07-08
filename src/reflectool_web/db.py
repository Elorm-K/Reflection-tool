"""SQLite connection helper: WAL mode, foreign keys, idempotent schema."""

import sqlite3
from importlib import resources
from pathlib import Path


def connect(db_path: str) -> sqlite3.Connection:
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    schema = resources.files("reflectool_web").joinpath("schema.sql").read_text()
    conn.executescript(schema)
    conn.commit()
    return conn
