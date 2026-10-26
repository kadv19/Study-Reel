"""PostgreSQL persistence for InstaClone feed posts."""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_init_lock = threading.Lock()
_initialized: set[str] = set()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_cloudinary_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except (TypeError, ValueError):
        return False
    return parsed.scheme == "https" and parsed.hostname == "res.cloudinary.com"


def _table_name(table: str | None = None) -> str:
    name = table or os.getenv("POSTS_TABLE", "posts")
    if not _TABLE_RE.fullmatch(name):
        raise ValueError(f"Invalid posts table name: {name!r}")
    return name


def _connect():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is required for InstaClone posts storage")
    return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)


def init_posts_db(table: str | None = None) -> None:
    name = _table_name(table)
    with _init_lock:
        if name in _initialized:
            return
        conn = _connect()
        try:
            cur = conn.cursor()
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {name} (
                    post_id TEXT PRIMARY KEY,
                    media_id TEXT,
                    slides JSONB NOT NULL DEFAULT '[]'::jsonb,
                    caption TEXT NOT NULL DEFAULT '',
                    hashtags JSONB NOT NULL DEFAULT '[]'::jsonb,
                    cover_slide INTEGER NOT NULL DEFAULT 0,
                    likes INTEGER NOT NULL DEFAULT 0,
                    views INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{name}_created_at ON {name}(created_at DESC)"
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{name}_media_id ON {name}(media_id)"
            )
            conn.commit()
            _initialized.add(name)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def drop_posts_table(table: str | None = None) -> None:
    name = _table_name(table)
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(f"DROP TABLE IF EXISTS {name}")
        conn.commit()
        _initialized.discard(name)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure(table: str | None = None) -> str:
    name = _table_name(table)
    if name not in _initialized:
        init_posts_db(name)
    return name


def _row_to_post(row) -> dict:
    return {
        "post_id": row["post_id"],
        "media_id": row["media_id"],
        "slides": row["slides"] or [],
        "caption": row["caption"] or "",
        "hashtags": row["hashtags"] or [],
        "cover_slide": row["cover_slide"],
        "likes": row["likes"],
        "views": row["views"],
        "created_at": row["created_at"],
    }


def upsert_post(post: dict, table: str | None = None) -> dict:
    name = _ensure(table)
    post_id = str(post.get("post_id") or "").strip()
    if not post_id:
        raise ValueError("post_id is required")
    media_id = str(post.get("media_id") or post_id)
    slides = post.get("slides") or []
    caption = post.get("caption") or ""
    hashtags = post.get("hashtags") or []
    cover_slide = int(post.get("cover_slide") or 0)
    likes = int(post.get("likes") or 0)
    views = int(post.get("views") or 0)
    created_at = str(post.get("created_at") or _now())
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            INSERT INTO {name}
                (post_id, media_id, slides, caption, hashtags, cover_slide, likes, views, created_at)
            VALUES (%s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s, %s)
            ON CONFLICT (post_id) DO UPDATE SET
                media_id = EXCLUDED.media_id,
                slides = EXCLUDED.slides,
                caption = EXCLUDED.caption,
                hashtags = EXCLUDED.hashtags,
                cover_slide = EXCLUDED.cover_slide
            RETURNING *
            """,
            (
                post_id,
                media_id,
                json.dumps(slides),
                caption,
                json.dumps(hashtags),
                cover_slide,
                likes,
                views,
                created_at,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return _row_to_post(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def increment_interaction(
    media_id: str, action: str, table: str | None = None
) -> dict | None:
    name = _ensure(table)
    column = "likes" if action == "like" else "views" if action == "view" else None
    if column is None:
        raise ValueError(f"Invalid action: {action}")
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE {name} SET {column} = {column} + 1 "
            "WHERE post_id = %s OR media_id = %s RETURNING likes, views",
            (media_id, media_id),
        )
        row = cur.fetchone()
        conn.commit()
        return {"likes": row["likes"], "views": row["views"]} if row else None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_posts(table: str | None = None) -> list[dict]:
    name = _ensure(table)
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {name} ORDER BY created_at DESC")
        rows = cur.fetchall()
    finally:
        conn.close()
    return [_row_to_post(row) for row in rows]


def get_post(media_id: str, table: str | None = None) -> dict | None:
    name = _ensure(table)
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM {name} WHERE post_id = %s OR media_id = %s LIMIT 1",
            (media_id, media_id),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    return _row_to_post(row) if row else None
