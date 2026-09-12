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

CREATE TABLE IF NOT EXISTS user_card_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    carousel_id INTEGER NOT NULL,
    slide_index INTEGER NOT NULL,
    card_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('review','catalog','mastered')),
    filed_at TEXT,
    last_shown_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, card_key)
);
CREATE INDEX IF NOT EXISTS idx_user_card_states_user ON user_card_states(user_id);
CREATE INDEX IF NOT EXISTS idx_user_card_states_state ON user_card_states(user_id, status);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
    email TEXT NOT NULL CHECK (email LIKE '%@%.%'),
    college TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(email)
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS colleges (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL UNIQUE
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
        # seed colleges dropdown (clean list, reject other free text)
        colleges = [
            ("vtu_belgaum", "VTU Belgaum"),
            ("bmsce", "BMSCE"),
            ("rvce", "RVCE"),
            ("pes_university", "PES University"),
            ("msrit", "MSRIT"),
            ("dsce", "DSCE"),
            ("other", "Other"),
        ]
        for code, label in colleges:
            conn.execute("INSERT OR IGNORE INTO colleges (code, label) VALUES (?, ?)", (code, label))


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


# ---- Card Catalog helpers (PDF §3) ----------------------------------------


def upsert_card_state(
    user_id: str, carousel_id: int, slide_index: int, status: str,
    db_path: str | Path | None = None,
) -> dict:
    card_key = f"{carousel_id}:{slide_index}"
    now = _now()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO user_card_states (user_id, carousel_id, slide_index, card_key, status, filed_at, last_shown_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, card_key) DO UPDATE SET status=excluded.status, filed_at=excluded.filed_at, last_shown_at=excluded.last_shown_at, updated_at=excluded.updated_at
            """,
            (user_id, carousel_id, slide_index, card_key, status, now, now, now),
        )
        row = conn.execute("SELECT * FROM user_card_states WHERE user_id=? AND card_key=?", (user_id, card_key)).fetchone()
    return dict(row) if row else {}


def list_card_states(user_id: str, status: str | None = None, db_path: str | Path | None = None) -> list[dict]:
    with _connect(db_path) as conn:
        if status:
            rows = conn.execute("SELECT * FROM user_card_states WHERE user_id=? AND status=? ORDER BY filed_at DESC", (user_id, status)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM user_card_states WHERE user_id=? ORDER BY filed_at DESC", (user_id,)).fetchall()
    return [dict(r) for r in rows]


def get_shelf_summary(user_id: str, db_path: str | Path | None = None) -> list[dict]:
    """Per-carousel shelf summary: total, mastered, fill_pct."""
    with _connect(db_path) as conn:
        carousels = conn.execute("SELECT id, carousel_json FROM carousels ORDER BY id DESC").fetchall()
        states = conn.execute("SELECT card_key, status FROM user_card_states WHERE user_id=?", (user_id,)).fetchall()
    status_map = {r["card_key"]: r["status"] for r in states}
    shelves = []
    for row in carousels:
        try:
            data = json.loads(row["carousel_json"])
            total = len(data.get("slides", []))
            mastered = sum(1 for i in range(total) if status_map.get(f"{row['id']}:{i}") == "mastered")
            fill = mastered / total if total else 0
            shelves.append({
                "shelf_id": str(row["id"]),
                "label": data.get("module_name", f"Carousel {row['id']}")[:12],
                "module_name": data.get("module_name", ""),
                "carousel_id": row["id"],
                "total_slides": total,
                "mastered_count": mastered,
                "fill_pct": round(fill, 3),
            })
        except Exception:
            continue
    # If no carousels yet, seed shelves from modules for demo
    if not shelves:
        with _connect(db_path) as conn:
            mods = conn.execute("SELECT topic_json FROM modules ORDER BY id DESC LIMIT 6").fetchall()
        for m in mods:
            try:
                t = json.loads(m["topic_json"])
                shelves.append({"shelf_id": f"mod_{t.get('module_number')}", "label": (t.get("module_title") or f"Mod {t.get('module_number')}")[:10], "module_name": t.get("module_title") or "", "carousel_id": None, "total_slides": len(t.get("topic_strings", [])), "mastered_count": 0, "fill_pct": 0})
            except:
                continue
    return shelves


# ---- Pseudonymous accounts (C) -------------------------------------------


def upsert_user(name: str, email: str, college: str, db_path: str | Path | None = None) -> dict:
    import uuid
    email = email.strip().lower()
    now = _now()
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE lower(email)=lower(?)", (email,)).fetchone()
        if row:
            # update name/college, keep id
            conn.execute("UPDATE users SET name=?, college=?, updated_at=? WHERE lower(email)=lower(?)", (name.strip(), college, now, email))
            row = conn.execute("SELECT * FROM users WHERE lower(email)=lower(?)", (email,)).fetchone()
            return dict(row)
        uid = uuid.uuid4().hex
        conn.execute("INSERT INTO users (id, name, email, college, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)", (uid, name.strip(), email, college, now, now))
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return dict(row) if row else {}


def get_user_by_id(user_id: str, db_path: str | Path | None = None) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_email(email: str, db_path: str | Path | None = None) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE lower(email)=lower(?)", (email.strip().lower(),)).fetchone()
    return dict(row) if row else None


def list_colleges(db_path: str | Path | None = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT code, label FROM colleges ORDER BY label").fetchall()
    return [dict(r) for r in rows]


def migrate_anon_cards(old_id: str, new_id: str, db_path: str | Path | None = None) -> int:
    if not old_id or not new_id or old_id == new_id:
        return 0
    with _connect(db_path) as conn:
        # move cards, ignore conflicts (keep new's version)
        cur = conn.execute("UPDATE OR IGNORE user_card_states SET user_id=?, updated_at=? WHERE user_id=?", (new_id, _now(), old_id))
        return cur.rowcount