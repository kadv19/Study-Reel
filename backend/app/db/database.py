"""SQLite persistence: syllabi, modules, carousels, pipeline state."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.schemas import Carousel, Syllabus

_DEFAULT_DB = Path(__file__).resolve().parents[2] / "studyreel.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS syllabi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    total_pages INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    syllabus_id INTEGER NOT NULL REFERENCES syllabi(id) ON DELETE CASCADE,
    module_number INTEGER NOT NULL,
    topic_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS carousels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    carousel_json TEXT NOT NULL,
    output_dir TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    state TEXT NOT NULL DEFAULT 'IDLE',
    stage TEXT,
    progress REAL NOT NULL DEFAULT 0.0,
    message TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
"""


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else _DEFAULT_DB
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO pipeline_state (id, state, updated_at) VALUES (1, 'IDLE', ?)",
            (_now(),),
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_syllabus(syllabus: Syllabus, db_path: str | Path | None = None) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO syllabi (file_name, total_pages, created_at) VALUES (?, ?, ?)",
            (syllabus.file_name, syllabus.total_pages, _now()),
        )
        syllabus_id = cur.lastrowid
        for module in syllabus.modules:
            conn.execute(
                "INSERT INTO modules (syllabus_id, module_number, topic_json) VALUES (?, ?, ?)",
                (syllabus_id, module.module_number, json.dumps(module.model_dump())),
            )
    return syllabus_id


def save_carousel(
    carousel: Carousel, module_id: int, output_dir: str | None = None,
    db_path: str | Path | None = None,
) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO carousels (module_id, carousel_json, output_dir, created_at) VALUES (?, ?, ?, ?)",
            (module_id, carousel.model_dump_json(), output_dir, _now()),
        )
    return cur.lastrowid


def get_module(module_number: int, db_path: str | Path | None = None) -> dict | None:
    """Fetch the module with the given number from the most recent syllabus."""
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT m.id, m.module_number, m.topic_json
            FROM modules m
            JOIN syllabi s ON s.id = m.syllabus_id
            WHERE m.module_number = ?
            ORDER BY s.id DESC
            LIMIT 1
            """,
            (module_number,),
        ).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "module_number": row["module_number"], "module": json.loads(row["topic_json"])}


def get_carousel(carousel_id: int, db_path: str | Path | None = None) -> dict | None:
    """Fetch a stored carousel by id (carousel_json + output_dir)."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, carousel_json, output_dir FROM carousels WHERE id = ?",
            (carousel_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "carousel": json.loads(row["carousel_json"]),
        "output_dir": row["output_dir"],
    }


def get_pipeline_state(db_path: str | Path | None = None) -> dict:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM pipeline_state WHERE id = 1").fetchone()
    return dict(row) if row else {}


def set_pipeline_state(
    state: str, stage: str | None, progress: float, message: str = "",
    db_path: str | Path | None = None,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE pipeline_state
            SET state = ?, stage = ?, progress = ?, message = ?, updated_at = ?
            WHERE id = 1
            """,
            (state, stage, progress, message, _now()),
        )