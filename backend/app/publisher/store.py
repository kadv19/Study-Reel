"""SQLite persistence for the publish pipeline: published posts, scheduled
posts, and the simulated OAuth token store."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

_DEFAULT_DB = Path(__file__).resolve().parents[2] / "studyreel_publisher.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS published_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    media_id TEXT NOT NULL,
    carousel_id INTEGER NOT NULL,
    caption TEXT,
    hashtags TEXT,
    feed_url TEXT,
    published_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scheduled_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    carousel_id INTEGER NOT NULL,
    caption TEXT,
    hashtags TEXT,
    schedule_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    token TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""

TOKEN_LIFETIME_DAYS = 60


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else _DEFAULT_DB
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_publisher_db(db_path: str | Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)


def save_published_post(
    provider: str, media_id: str, carousel_id: int,
    caption: str | None, hashtags: list[str], feed_url: str,
    db_path: str | Path | None = None,
) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO published_posts
               (provider, media_id, carousel_id, caption, hashtags, feed_url, published_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (provider, media_id, carousel_id, caption, json.dumps(hashtags),
             feed_url, _now()),
        )
        return cur.lastrowid


def list_published_posts(db_path: str | Path | None = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM published_posts ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def save_scheduled_post(
    carousel_id: int, caption: str | None, hashtags: list[str],
    schedule_at: str, db_path: str | Path | None = None,
) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO scheduled_posts
               (carousel_id, caption, hashtags, schedule_at, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (carousel_id, caption, json.dumps(hashtags), schedule_at, _now()),
        )
        return cur.lastrowid


def due_scheduled_posts(db_path: str | Path | None = None) -> list[dict]:
    now_iso = _now()
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM scheduled_posts WHERE schedule_at <= ? ORDER BY schedule_at ASC",
            (now_iso,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_scheduled_post(post_id: int, db_path: str | Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM scheduled_posts WHERE id = ?", (post_id,))


def save_oauth_token(db_path: str | Path | None = None) -> dict:
    import uuid
    token = uuid.uuid4().hex
    expires_at = (datetime.now(timezone.utc) + timedelta(days=TOKEN_LIFETIME_DAYS)).isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO oauth_tokens (id, token, expires_at) VALUES (1, ?, ?)",
            (token, expires_at),
        )
    return {"token": token, "expires_at": expires_at}


def get_oauth_token(db_path: str | Path | None = None) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM oauth_tokens WHERE id = 1").fetchone()
    return dict(row) if row else None


def clear_oauth_token(db_path: str | Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM oauth_tokens WHERE id = 1")


def is_oauth_connected(db_path: str | Path | None = None) -> bool:
    tok = get_oauth_token(db_path)
    if not tok:
        return False
    exp = datetime.fromisoformat(tok["expires_at"])
    return exp > datetime.now(timezone.utc)
