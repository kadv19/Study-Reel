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
    owner_user_id TEXT,
    resource_text TEXT,
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
    password_hash TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(email)
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS colleges (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
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
        # migrate existing users table to add password_hash if missing (existing rows -> NULL)
        try:
            conn.execute("SELECT password_hash FROM users LIMIT 1")
        except sqlite3.OperationalError:
            try:
                conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
            except Exception:
                pass
        # migrate syllabi to add owner_user_id if missing (existing rows -> NULL)
        try:
            conn.execute("SELECT owner_user_id FROM syllabi LIMIT 1")
        except sqlite3.OperationalError:
            try:
                conn.execute("ALTER TABLE syllabi ADD COLUMN owner_user_id TEXT")
            except Exception:
                pass
        # migrate syllabi to add resource_text if missing (existing rows -> NULL)
        try:
            conn.execute("SELECT resource_text FROM syllabi LIMIT 1")
        except sqlite3.OperationalError:
            try:
                conn.execute("ALTER TABLE syllabi ADD COLUMN resource_text TEXT")
            except Exception:
                pass
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_syllabi_owner ON syllabi(owner_user_id)")
        except Exception:
            pass
        # also ensure sessions table exists for old DBs
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)")
        conn.execute(
            "INSERT OR IGNORE INTO pipeline_state (id, state, updated_at) VALUES (1, 'IDLE', ?)",
            (_now(),),
        )
        # seed colleges dropdown — new primary colleges (NIE, VVCE, SJCE)
        colleges = [
            ("NIE", "NIE"),
            ("VVCE", "VVCE"),
            ("SJCE", "SJCE"),
        ]
        for code, label in colleges:
            conn.execute("INSERT OR IGNORE INTO colleges (code, label) VALUES (?, ?)", (code, label))
        # clean up old seeded colleges not in new allowed list (keep user rows untouched)
        try:
            conn.execute("DELETE FROM colleges WHERE code NOT IN ('NIE','VVCE','SJCE')")
        except Exception:
            pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_syllabus(syllabus: Syllabus, owner_user_id: str | None = None, resource_text: str | None = None, db_path: str | Path | None = None) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO syllabi (file_name, total_pages, owner_user_id, resource_text, created_at) VALUES (?, ?, ?, ?, ?)",
            (syllabus.file_name, syllabus.total_pages, owner_user_id, resource_text, _now()),
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
            SELECT m.id, m.module_number, m.topic_json, s.resource_text, s.id as syllabus_id
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
    return {"id": row["id"], "module_number": row["module_number"], "module": json.loads(row["topic_json"]), "resource_text": row["resource_text"], "syllabus_id": row["syllabus_id"]}


def get_resource_text_for_syllabus(syllabus_id: int, db_path: str | Path | None = None) -> str | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT resource_text FROM syllabi WHERE id=?", (syllabus_id,)).fetchone()
    return row["resource_text"] if row and row["resource_text"] else None


def get_syllabus_by_id(syllabus_id: int, db_path: str | Path | None = None) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT id, file_name, total_pages, owner_user_id, resource_text, created_at FROM syllabi WHERE id=?", (syllabus_id,)).fetchone()
    return dict(row) if row else None


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


def _clean_book_label(file_name: str) -> str:
    """Clean syllabus filename for book cover: stem without ' Syllabus' suffix."""
    stem = Path(file_name).stem.strip()
    if stem.lower().endswith(" syllabus"):
        stem = stem[: -len(" syllabus")].strip()
    # also strip trailing _... or UUID prefix if present? keep as-is
    return stem or file_name

def get_shelf_summary(user_id: str, db_path: str | Path | None = None) -> list[dict]:
    """Per-carousel shelf summary: total, mastered, fill_pct — owner-scoped."""
    with _connect(db_path) as conn:
        carousels = conn.execute(
            """
            SELECT c.id, c.carousel_json, s.file_name, s.id as syllabus_id
            FROM carousels c
            JOIN modules m ON m.id = c.module_id
            JOIN syllabi s ON s.id = m.syllabus_id
            WHERE s.owner_user_id = ?
            ORDER BY s.id DESC, c.id DESC
            """,
            (user_id,),
        ).fetchall()
        states = conn.execute("SELECT card_key, status FROM user_card_states WHERE user_id=?", (user_id,)).fetchall()
    status_map = {r["card_key"]: r["status"] for r in states}
    shelves = []
    for row in carousels:
        try:
            data = json.loads(row["carousel_json"])
            total = len(data.get("slides", []))
            mastered = sum(1 for i in range(total) if status_map.get(f"{row['id']}:{i}") == "mastered")
            fill = mastered / total if total else 0
            raw_label = data.get("module_name", f"Carousel {row['id']}")
            label = raw_label
            if raw_label.strip().lower().startswith("module ") and len(raw_label.strip().split()) == 2:
                stem = _clean_book_label(row["file_name"])
                label = f"{stem} — {raw_label}"
            book_label = _clean_book_label(row["file_name"])
            shelves.append({
                "shelf_id": str(row["id"]),
                "label": label,
                "module_name": data.get("module_name", ""),
                "carousel_id": row["id"],
                "total_slides": total,
                "mastered_count": mastered,
                "fill_pct": round(fill, 3),
                "syllabus_id": row["syllabus_id"],
                "book_label": book_label,
                "file_name": row["file_name"],
            })
        except Exception:
            continue
    # If no owned carousels yet, show generic starter from owned modules only (privacy)
    if not shelves:
        with _connect(db_path) as conn:
            mods = conn.execute(
                """
                SELECT m.topic_json, s.file_name, s.id as syllabus_id
                FROM modules m
                JOIN syllabi s ON s.id = m.syllabus_id
                WHERE s.owner_user_id = ?
                ORDER BY m.id DESC LIMIT 6
                """,
                (user_id,),
            ).fetchall()
        for m in mods:
            try:
                t = json.loads(m["topic_json"])
                raw_label = t.get("module_title") or f"Mod {t.get('module_number')}"
                label = raw_label
                if not t.get("module_title"):
                    stem = _clean_book_label(m["file_name"])
                    label = f"{stem} — {raw_label}"
                book_label = _clean_book_label(m["file_name"])
                shelves.append({
                    "shelf_id": f"mod_{t.get('module_number')}",
                    "label": label,
                    "module_name": t.get("module_title") or "",
                    "carousel_id": None,
                    "total_slides": len(t.get("topic_strings", [])),
                    "mastered_count": 0,
                    "fill_pct": 0,
                    "syllabus_id": m["syllabus_id"],
                    "book_label": book_label,
                    "file_name": m["file_name"],
                })
            except:
                continue
    return shelves


def get_library_summary(user_id: str, db_path: str | Path | None = None) -> list[dict]:
    """Books = owned syllabi, each with aggregated progress across its carousels."""
    with _connect(db_path) as conn:
        syllabi = conn.execute(
            "SELECT id, file_name, created_at FROM syllabi WHERE owner_user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        # pre-fetch all shelves for aggregation
        shelves = get_shelf_summary(user_id, db_path=db_path)
        # group shelves by syllabus_id (include fallback module shelves)
        from collections import defaultdict
        by_book = defaultdict(list)
        for sh in shelves:
            by_book[sh["syllabus_id"]].append(sh)
        states = conn.execute("SELECT card_key, status FROM user_card_states WHERE user_id=?", (user_id,)).fetchall()
        status_map = {r["card_key"]: r["status"] for r in states}
        # need also modules for shelf counts when no shelves yet (should not happen if fallback exists, but keep)
        mods_by_syl = defaultdict(list)
        if not shelves:
            mods = conn.execute(
                "SELECT m.topic_json, s.id as sid FROM modules m JOIN syllabi s ON s.id=m.syllabus_id WHERE s.owner_user_id=?",
                (user_id,),
            ).fetchall()
            for r in mods:
                try:
                    tj = json.loads(r["topic_json"])
                    mods_by_syl[r["sid"]].append(tj)
                except:
                    continue
    books = []
    for row in syllabi:
        sid = row["id"]
        book_label = _clean_book_label(row["file_name"])
        shs = by_book.get(sid, [])
        if shs:
            total = sum(s["total_slides"] for s in shs)
            mastered = sum(s["mastered_count"] for s in shs)
            fill = mastered / total if total else 0
            shelf_count = len(shs)
        else:
            # no carousels yet — count modules
            mlist = mods_by_syl.get(sid, [])
            if mlist:
                total = sum(len(m.get("topic_strings", [])) for m in mlist)
                shelf_count = len(mlist)
                fill = 0
                mastered = 0
            else:
                # syllabus with no modules? skip
                total = 0
                shelf_count = 0
                fill = 0
                mastered = 0
        books.append({
            "book_id": str(sid),
            "syllabus_id": sid,
            "label": book_label,
            "file_name": row["file_name"],
            "created_at": row["created_at"],
            "total_slides": total,
            "mastered_count": mastered,
            "fill_pct": round(fill, 3),
            "shelf_count": shelf_count,
            "shelves": shs,  # embed for convenience
        })
    # sort by fill maybe? keep DESC created
    return books


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


# ---- Real auth (password_hash + sessions) --------------------------------


def create_user_with_password(name: str, email: str, college: str, password_hash: str, db_path: str | Path | None = None) -> dict:
    import uuid
    email = email.strip().lower()
    college = college.strip().upper()
    now = _now()
    uid = uuid.uuid4().hex
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (id, name, email, college, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, name.strip(), email, college, password_hash, now, now),
        )
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return dict(row) if row else {}


def create_session(user_id: str, db_path: str | Path | None = None) -> str:
    import secrets
    token = secrets.token_hex(32)
    now = _now()
    with _connect(db_path) as conn:
        conn.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user_id, now))
    return token


def get_user_by_token(token: str, db_path: str | Path | None = None) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT u.* FROM users u JOIN sessions s ON s.user_id = u.id WHERE s.token = ?", (token,)
        ).fetchone()
    return dict(row) if row else None


def get_session(token: str, db_path: str | Path | None = None) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    return dict(row) if row else None


def delete_session(token: str, db_path: str | Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))