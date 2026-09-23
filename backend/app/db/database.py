"""PostgreSQL persistence: syllabi, modules, carousels, pipeline state."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras

from app.schemas import Carousel, Syllabus

_DEFAULT_DB = Path(__file__).resolve().parents[2] / "studyreel.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS syllabi (
    id SERIAL PRIMARY KEY,
    file_name TEXT NOT NULL,
    total_pages INTEGER NOT NULL,
    owner_user_id TEXT,
    resource_text TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS modules (
    id SERIAL PRIMARY KEY,
    syllabus_id INTEGER NOT NULL REFERENCES syllabi(id) ON DELETE CASCADE,
    module_number INTEGER NOT NULL,
    topic_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS carousels (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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


def _connect(db_path: str | Path | None = None):
    # db_path kept for API compatibility but ignored — always use DATABASE_URL
    dsn = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def _exec(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur


def init_db(db_path: str | Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        # executescript equivalent: split on ; and run each statement
        # psycopg2 can handle the whole SCHEMA in one execute for table creation,
        # but we execute as a whole to keep indexes atomic.
        # Fallback to splitting if driver complains.
        try:
            cur.execute(SCHEMA)
        except Exception:
            conn.rollback()
            # split fallback
            for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
                cur = conn.cursor()
                cur.execute(stmt)
        # migration: users.password_hash
        cur = _exec(conn, "SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='password_hash'")
        if not cur.fetchone():
            try:
                _exec(conn, "ALTER TABLE users ADD COLUMN password_hash TEXT")
            except Exception:
                conn.rollback()
        # migration: syllabi.owner_user_id
        cur = _exec(conn, "SELECT column_name FROM information_schema.columns WHERE table_name='syllabi' AND column_name='owner_user_id'")
        if not cur.fetchone():
            try:
                _exec(conn, "ALTER TABLE syllabi ADD COLUMN owner_user_id TEXT")
            except Exception:
                conn.rollback()
        # migration: syllabi.resource_text
        cur = _exec(conn, "SELECT column_name FROM information_schema.columns WHERE table_name='syllabi' AND column_name='resource_text'")
        if not cur.fetchone():
            try:
                _exec(conn, "ALTER TABLE syllabi ADD COLUMN resource_text TEXT")
            except Exception:
                conn.rollback()
        try:
            _exec(conn, "CREATE INDEX IF NOT EXISTS idx_syllabi_owner ON syllabi(owner_user_id)")
        except Exception:
            conn.rollback()
        # also ensure sessions table exists for old DBs
        _exec(
            conn,
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL
            )
            """,
        )
        _exec(conn, "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        _exec(conn, "CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)")
        _exec(
            conn,
            "INSERT INTO pipeline_state (id, state, updated_at) VALUES (1, 'IDLE', %s) ON CONFLICT (id) DO NOTHING",
            (_now(),),
        )
        # seed colleges dropdown — new primary colleges (NIE, VVCE, SJCE)
        colleges = [
            ("NIE", "NIE"),
            ("VVCE", "VVCE"),
            ("SJCE", "SJCE"),
        ]
        for code, label in colleges:
            _exec(conn, "INSERT INTO colleges (code, label) VALUES (%s, %s) ON CONFLICT DO NOTHING", (code, label))
        # clean up old seeded colleges not in new allowed list (keep user rows untouched)
        try:
            _exec(conn, "DELETE FROM colleges WHERE code NOT IN ('NIE','VVCE','SJCE')")
        except Exception:
            conn.rollback()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_syllabus(syllabus: Syllabus, owner_user_id: str | None = None, resource_text: str | None = None, db_path: str | Path | None = None) -> int:
    conn = _connect(db_path)
    try:
        cur = _exec(
            conn,
            "INSERT INTO syllabi (file_name, total_pages, owner_user_id, resource_text, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (syllabus.file_name, syllabus.total_pages, owner_user_id, resource_text, _now()),
        )
        row = cur.fetchone()
        syllabus_id = row["id"] if row else None
        for module in syllabus.modules:
            _exec(
                conn,
                "INSERT INTO modules (syllabus_id, module_number, topic_json) VALUES (%s, %s, %s)",
                (syllabus_id, module.module_number, json.dumps(module.model_dump())),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return syllabus_id


def save_carousel(
    carousel: Carousel, module_id: int, output_dir: str | None = None,
    db_path: str | Path | None = None,
) -> int:
    conn = _connect(db_path)
    try:
        cur = _exec(
            conn,
            "INSERT INTO carousels (module_id, carousel_json, output_dir, created_at) VALUES (%s, %s, %s, %s) RETURNING id",
            (module_id, carousel.model_dump_json(), output_dir, _now()),
        )
        row = cur.fetchone()
        cid = row["id"] if row else None
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return cid


def get_module(module_number: int, db_path: str | Path | None = None) -> dict | None:
    """Fetch the module with the given number from the most recent syllabus."""
    conn = _connect(db_path)
    try:
        cur = _exec(
            conn,
            """
            SELECT m.id, m.module_number, m.topic_json, s.resource_text, s.id as syllabus_id
            FROM modules m
            JOIN syllabi s ON s.id = m.syllabus_id
            WHERE m.module_number = %s
            ORDER BY s.id DESC
            LIMIT 1
            """,
            (module_number,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return {"id": row["id"], "module_number": row["module_number"], "module": json.loads(row["topic_json"]), "resource_text": row["resource_text"], "syllabus_id": row["syllabus_id"]}


def get_resource_text_for_syllabus(syllabus_id: int, db_path: str | Path | None = None) -> str | None:
    conn = _connect(db_path)
    try:
        cur = _exec(conn, "SELECT resource_text FROM syllabi WHERE id=%s", (syllabus_id,))
        row = cur.fetchone()
    finally:
        conn.close()
    return row["resource_text"] if row and row["resource_text"] else None


def get_syllabus_by_id(syllabus_id: int, db_path: str | Path | None = None) -> dict | None:
    conn = _connect(db_path)
    try:
        cur = _exec(conn, "SELECT id, file_name, total_pages, owner_user_id, resource_text, created_at FROM syllabi WHERE id=%s", (syllabus_id,))
        row = cur.fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def get_carousel(carousel_id: int, db_path: str | Path | None = None) -> dict | None:
    """Fetch a stored carousel by id (carousel_json + output_dir)."""
    conn = _connect(db_path)
    try:
        cur = _exec(
            conn,
            "SELECT id, carousel_json, output_dir FROM carousels WHERE id = %s",
            (carousel_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return {
        "id": row["id"],
        "carousel": json.loads(row["carousel_json"]),
        "output_dir": row["output_dir"],
    }


def get_pipeline_state(db_path: str | Path | None = None) -> dict:
    conn = _connect(db_path)
    try:
        cur = _exec(conn, "SELECT * FROM pipeline_state WHERE id = 1")
        row = cur.fetchone()
    finally:
        conn.close()
    return dict(row) if row else {}


def set_pipeline_state(
    state: str, stage: str | None, progress: float, message: str = "",
    db_path: str | Path | None = None,
) -> None:
    conn = _connect(db_path)
    try:
        _exec(
            conn,
            """
            UPDATE pipeline_state
            SET state = %s, stage = %s, progress = %s, message = %s, updated_at = %s
            WHERE id = 1
            """,
            (state, stage, progress, message, _now()),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---- Card Catalog helpers (PDF §3) ----------------------------------------


def upsert_card_state(
    user_id: str, carousel_id: int, slide_index: int, status: str,
    db_path: str | Path | None = None,
) -> dict:
    card_key = f"{carousel_id}:{slide_index}"
    now = _now()
    conn = _connect(db_path)
    try:
        _exec(
            conn,
            """
            INSERT INTO user_card_states (user_id, carousel_id, slide_index, card_key, status, filed_at, last_shown_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(user_id, card_key) DO UPDATE SET status=excluded.status, filed_at=excluded.filed_at, last_shown_at=excluded.last_shown_at, updated_at=excluded.updated_at
            """,
            (user_id, carousel_id, slide_index, card_key, status, now, now, now),
        )
        conn.commit()
        cur = _exec(conn, "SELECT * FROM user_card_states WHERE user_id=%s AND card_key=%s", (user_id, card_key))
        row = cur.fetchone()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return dict(row) if row else {}


def list_card_states(user_id: str, status: str | None = None, db_path: str | Path | None = None) -> list[dict]:
    conn = _connect(db_path)
    try:
        if status:
            cur = _exec(conn, "SELECT * FROM user_card_states WHERE user_id=%s AND status=%s ORDER BY filed_at DESC", (user_id, status))
            rows = cur.fetchall()
        else:
            cur = _exec(conn, "SELECT * FROM user_card_states WHERE user_id=%s ORDER BY filed_at DESC", (user_id,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _clean_book_label(file_name: str) -> str:
    """Clean syllabus filename for book cover: stem without ' Syllabus' suffix."""
    stem = Path(file_name).stem.strip()
    if stem.lower().endswith(" syllabus"):
        stem = stem[: -len(" syllabus")].strip()
    # also strip trailing _... or UUID prefix if present? keep as-is
    return stem or file_name


# Seed demo books for cold-start when user has no owned data — AI/EV/Aero as discussed
_SEED_SHELVES = [
    {"shelf_id": "seed_ai_1", "label": "Transformer Architecture", "module_name": "Transformer Architecture", "carousel_id": None, "total_slides": 4, "mastered_count": 0, "fill_pct": 0, "syllabus_id": "seed_ai", "book_label": "AI Fundamentals", "file_name": "AI Discovery", "is_seed": True},
    {"shelf_id": "seed_ai_2", "label": "RAG Pipeline", "module_name": "RAG Pipeline", "carousel_id": None, "total_slides": 3, "mastered_count": 0, "fill_pct": 0, "syllabus_id": "seed_ai", "book_label": "AI Fundamentals", "file_name": "AI Discovery", "is_seed": True},
    {"shelf_id": "seed_ev_1", "label": "BLDC Motor Control", "module_name": "BLDC Motor Control", "carousel_id": None, "total_slides": 3, "mastered_count": 0, "fill_pct": 0, "syllabus_id": "seed_ev", "book_label": "EV Systems", "file_name": "EV Discovery", "is_seed": True},
    {"shelf_id": "seed_ev_2", "label": "Battery Management", "module_name": "Battery Management", "carousel_id": None, "total_slides": 3, "mastered_count": 0, "fill_pct": 0, "syllabus_id": "seed_ev", "book_label": "EV Systems", "file_name": "EV Discovery", "is_seed": True},
    {"shelf_id": "seed_aero_1", "label": "Lift & Drag", "module_name": "Lift & Drag", "carousel_id": None, "total_slides": 3, "mastered_count": 0, "fill_pct": 0, "syllabus_id": "seed_aero", "book_label": "Aerodynamics", "file_name": "Aero Discovery", "is_seed": True},
    {"shelf_id": "seed_aero_2", "label": "Polar Curve", "module_name": "Polar Curve", "carousel_id": None, "total_slides": 2, "mastered_count": 0, "fill_pct": 0, "syllabus_id": "seed_aero", "book_label": "Aerodynamics", "file_name": "Aero Discovery", "is_seed": True},
    {"shelf_id": "seed_cs_1", "label": "OS Scheduling", "module_name": "OS Scheduling", "carousel_id": None, "total_slides": 3, "mastered_count": 0, "fill_pct": 0, "syllabus_id": "seed_cs", "book_label": "CS Fundamentals", "file_name": "CS Discovery", "is_seed": True},
    {"shelf_id": "seed_cs_2", "label": "Indexing Strategies", "module_name": "Indexing Strategies", "carousel_id": None, "total_slides": 2, "mastered_count": 0, "fill_pct": 0, "syllabus_id": "seed_cs", "book_label": "CS Fundamentals", "file_name": "CS Discovery", "is_seed": True},
]
_SEED_BOOKS = [
    {"book_id": "seed_ai", "syllabus_id": "seed_ai", "label": "AI Fundamentals", "file_name": "AI Discovery", "created_at": "2024-01-01T00:00:00+00:00", "total_slides": 7, "mastered_count": 0, "fill_pct": 0, "shelf_count": 2, "is_seed": True, "shelves": [_SEED_SHELVES[0], _SEED_SHELVES[1]]},
    {"book_id": "seed_ev", "syllabus_id": "seed_ev", "label": "EV Systems", "file_name": "EV Discovery", "created_at": "2024-01-01T00:00:00+00:00", "total_slides": 6, "mastered_count": 0, "fill_pct": 0, "shelf_count": 2, "is_seed": True, "shelves": [_SEED_SHELVES[2], _SEED_SHELVES[3]]},
    {"book_id": "seed_aero", "syllabus_id": "seed_aero", "label": "Aerodynamics", "file_name": "Aero Discovery", "created_at": "2024-01-01T00:00:00+00:00", "total_slides": 5, "mastered_count": 0, "fill_pct": 0, "shelf_count": 2, "is_seed": True, "shelves": [_SEED_SHELVES[4], _SEED_SHELVES[5]]},
    {"book_id": "seed_cs", "syllabus_id": "seed_cs", "label": "CS Fundamentals", "file_name": "CS Discovery", "created_at": "2024-01-01T00:00:00+00:00", "total_slides": 5, "mastered_count": 0, "fill_pct": 0, "shelf_count": 2, "is_seed": True, "shelves": [_SEED_SHELVES[6], _SEED_SHELVES[7]]},
]

def get_shelf_summary(user_id: str, db_path: str | Path | None = None) -> list[dict]:
    """Per-carousel shelf summary: total, mastered, fill_pct — owner-scoped."""
    conn = _connect(db_path)
    try:
        cur = _exec(
            conn,
            """
            SELECT c.id, c.carousel_json, s.file_name, s.id as syllabus_id
            FROM carousels c
            JOIN modules m ON m.id = c.module_id
            JOIN syllabi s ON s.id = m.syllabus_id
            WHERE s.owner_user_id = %s
            ORDER BY s.id DESC, c.id DESC
            """,
            (user_id,),
        )
        carousels = cur.fetchall()
        cur = _exec(conn, "SELECT card_key, status FROM user_card_states WHERE user_id=%s", (user_id,))
        states = cur.fetchall()
    finally:
        conn.close()
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
                "is_seed": False,
            })
        except Exception:
            continue
    # If no owned carousels yet, show generic starter from owned modules only (privacy)
    if not shelves:
        conn = _connect(db_path)
        try:
            cur = _exec(
                conn,
                """
                SELECT m.topic_json, s.file_name, s.id as syllabus_id
                FROM modules m
                JOIN syllabi s ON s.id = m.syllabus_id
                WHERE s.owner_user_id = %s
                ORDER BY m.id DESC LIMIT 6
                """,
                (user_id,),
            )
            mods = cur.fetchall()
        finally:
            conn.close()
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
                    "is_seed": False,
                })
            except:
                continue
    # Always include global demo seeds (AI/EV/Aero/CS) alongside owned data — user asked for A for both (resource + seeds)
    # Seeds are marked is_seed=True and are read-only (no delete, demo deck)
    import copy
    # If user has no owned shelves at all, start with seeds; otherwise append seeds so library always shows discovery
    if not shelves:
        shelves = copy.deepcopy(_SEED_SHELVES)
    else:
        # append seeds so every library shows discovery (dedup by shelf_id not needed as owned ids are ints)
        shelves = shelves + copy.deepcopy(_SEED_SHELVES)
    return shelves


def get_library_summary(user_id: str, db_path: str | Path | None = None) -> list[dict]:
    """Books = owned syllabi, each with aggregated progress across its carousels."""
    conn = _connect(db_path)
    try:
        cur = _exec(
            conn,
            "SELECT id, file_name, created_at FROM syllabi WHERE owner_user_id = %s ORDER BY id DESC",
            (user_id,),
        )
        syllabi = cur.fetchall()
        # pre-fetch all shelves for aggregation
        shelves = get_shelf_summary(user_id, db_path=db_path)
        # group shelves by syllabus_id (include fallback module shelves)
        from collections import defaultdict
        by_book = defaultdict(list)
        for sh in shelves:
            by_book[sh["syllabus_id"]].append(sh)
        cur = _exec(conn, "SELECT card_key, status FROM user_card_states WHERE user_id=%s", (user_id,))
        states = cur.fetchall()
        status_map = {r["card_key"]: r["status"] for r in states}
        # need also modules for shelf counts when no shelves yet (should not happen if fallback exists, but keep)
        mods_by_syl = defaultdict(list)
        if not shelves:
            cur = _exec(
                conn,
                "SELECT m.topic_json, s.id as sid FROM modules m JOIN syllabi s ON s.id=m.syllabus_id WHERE s.owner_user_id=%s",
                (user_id,),
            )
            mods = cur.fetchall()
            for r in mods:
                try:
                    tj = json.loads(r["topic_json"])
                    mods_by_syl[r["sid"]].append(tj)
                except:
                    continue
    finally:
        conn.close()
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
            "is_seed": False,
            "shelves": shs,  # embed for convenience
        })
    # Always include global demo seeds alongside owned books (user asked for A for both)
    import copy
    if not books:
        # no owned books at all — return just seeds
        return copy.deepcopy(_SEED_BOOKS)
    # append seeds so every library shows discovery (AI/EV/Aero/CS) in addition to owned
    # Avoid double-counting if somehow owned already includes a seed id (should not happen as owned ids are ints)
    existing_ids = {b["book_id"] for b in books}
    for sb in _SEED_BOOKS:
        if sb["book_id"] not in existing_ids:
            books.append(copy.deepcopy(sb))
    # sort by is_seed last? Keep owned first, then seeds by label, but keep as is for now
    return books


# ---- Pseudonymous accounts (C) -------------------------------------------


def upsert_user(name: str, email: str, college: str, db_path: str | Path | None = None) -> dict:
    import uuid
    email = email.strip().lower()
    now = _now()
    conn = _connect(db_path)
    try:
        cur = _exec(conn, "SELECT * FROM users WHERE lower(email)=lower(%s)", (email,))
        row = cur.fetchone()
        if row:
            # update name/college, keep id
            _exec(conn, "UPDATE users SET name=%s, college=%s, updated_at=%s WHERE lower(email)=lower(%s)", (name.strip(), college, now, email))
            conn.commit()
            cur = _exec(conn, "SELECT * FROM users WHERE lower(email)=lower(%s)", (email,))
            row = cur.fetchone()
            return dict(row)
        uid = uuid.uuid4().hex
        _exec(conn, "INSERT INTO users (id, name, email, college, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s)", (uid, name.strip(), email, college, now, now))
        conn.commit()
        cur = _exec(conn, "SELECT * FROM users WHERE id=%s", (uid,))
        row = cur.fetchone()
        return dict(row) if row else {}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_user_by_id(user_id: str, db_path: str | Path | None = None) -> dict | None:
    conn = _connect(db_path)
    try:
        cur = _exec(conn, "SELECT * FROM users WHERE id=%s", (user_id,))
        row = cur.fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str, db_path: str | Path | None = None) -> dict | None:
    conn = _connect(db_path)
    try:
        cur = _exec(conn, "SELECT * FROM users WHERE lower(email)=lower(%s)", (email.strip().lower(),))
        row = cur.fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def list_colleges(db_path: str | Path | None = None) -> list[dict]:
    conn = _connect(db_path)
    try:
        cur = _exec(conn, "SELECT code, label FROM colleges ORDER BY label")
        rows = cur.fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def migrate_anon_cards(old_id: str, new_id: str, db_path: str | Path | None = None) -> int:
    if not old_id or not new_id or old_id == new_id:
        return 0
    conn = _connect(db_path)
    try:
        # move cards, ignore conflicts (keep new's version)
        # Postgres has no UPDATE OR IGNORE; emulate by only updating rows whose card_key doesn't already exist for new_id
        cur = _exec(
            conn,
            """
            UPDATE user_card_states
            SET user_id=%s, updated_at=%s
            WHERE user_id=%s
              AND card_key NOT IN (SELECT card_key FROM user_card_states WHERE user_id=%s)
            """,
            (new_id, _now(), old_id, new_id),
        )
        conn.commit()
        return cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---- Real auth (password_hash + sessions) --------------------------------


def create_user_with_password(name: str, email: str, college: str, password_hash: str, db_path: str | Path | None = None) -> dict:
    import uuid
    email = email.strip().lower()
    college = college.strip().upper()
    now = _now()
    uid = uuid.uuid4().hex
    conn = _connect(db_path)
    try:
        _exec(
            conn,
            "INSERT INTO users (id, name, email, college, password_hash, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (uid, name.strip(), email, college, password_hash, now, now),
        )
        conn.commit()
        cur = _exec(conn, "SELECT * FROM users WHERE id=%s", (uid,))
        row = cur.fetchone()
        return dict(row) if row else {}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_session(user_id: str, db_path: str | Path | None = None) -> str:
    import secrets
    token = secrets.token_hex(32)
    now = _now()
    conn = _connect(db_path)
    try:
        _exec(conn, "INSERT INTO sessions (token, user_id, created_at) VALUES (%s, %s, %s)", (token, user_id, now))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return token


def get_user_by_token(token: str, db_path: str | Path | None = None) -> dict | None:
    conn = _connect(db_path)
    try:
        cur = _exec(
            conn,
            "SELECT u.* FROM users u JOIN sessions s ON s.user_id = u.id WHERE s.token = %s", (token,)
        )
        row = cur.fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def get_session(token: str, db_path: str | Path | None = None) -> dict | None:
    conn = _connect(db_path)
    try:
        cur = _exec(conn, "SELECT * FROM sessions WHERE token = %s", (token,))
        row = cur.fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def delete_session(token: str, db_path: str | Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        _exec(conn, "DELETE FROM sessions WHERE token = %s", (token,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_syllabus(syllabus_id: int, owner_user_id: str, db_path: str | Path | None = None) -> bool:
    """Delete a syllabus (book) if owned by owner_user_id. Returns True if deleted."""
    import shutil
    conn = _connect(db_path)
    try:
        cur = _exec(conn, "SELECT id, owner_user_id FROM syllabi WHERE id=%s", (syllabus_id,))
        row = cur.fetchone()
        if not row:
            return False
        if row["owner_user_id"] != owner_user_id:
            return False
        # collect carousel output dirs and ids for cleanup
        cur = _exec(
            conn,
            "SELECT c.id, c.output_dir FROM carousels c JOIN modules m ON m.id=c.module_id WHERE m.syllabus_id=%s",
            (syllabus_id,),
        )
        carousels = cur.fetchall()
        carousel_ids = [r["id"] for r in carousels]
        output_dirs = [r["output_dir"] for r in carousels if r["output_dir"]]
        # delete user card states for those carousels
        if carousel_ids:
            placeholders = ",".join("%s" for _ in carousel_ids)
            _exec(conn, f"DELETE FROM user_card_states WHERE carousel_id IN ({placeholders})", tuple(carousel_ids))
        # delete syllabus (cascades to modules and carousels via FK)
        _exec(conn, "DELETE FROM syllabi WHERE id=%s", (syllabus_id,))
        conn.commit()
        # filesystem cleanup outside transaction
        for od in output_dirs:
            try:
                p = Path(od)
                if p.exists() and p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                elif p.exists():
                    p.unlink(missing_ok=True)
            except Exception:
                pass
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
