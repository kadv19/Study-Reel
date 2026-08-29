"""Phase 2 publish API: deliver carousels to the (simulated) platform, list
posts, and a simulated OAuth handshake. The Publisher abstraction means the
underlying target (InstaClone vs real Meta) is invisible to these routes.
"""

from __future__ import annotations

import json
import os
import threading
import time

from fastapi import APIRouter, HTTPException

from app.db.database import get_carousel
from app.publisher import get_publisher
from app.publisher.store import (
    clear_oauth_token,
    delete_scheduled_post,
    due_scheduled_posts,
    get_oauth_token,
    init_publisher_db,
    is_oauth_connected,
    list_published_posts,
    save_oauth_token,
    save_published_post,
    save_scheduled_post,
)
from app.schemas import Carousel, PostMetadata, PublishRequest

router = APIRouter(prefix="/api/v2", tags=["publish"])


def _db_path() -> str | None:
    return os.getenv("PUBLISHER_DB", None)


_scheduler_started = False
_scheduler_lock = threading.Lock()


@router.post("/publish")
def publish(payload: PublishRequest) -> dict:
    record = get_carousel(payload.carousel_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Carousel {payload.carousel_id} not found — render it first",
        )

    carousel = Carousel(**record["carousel"])
    output_dir = __import__("pathlib").Path(record["output_dir"])
    metadata = PostMetadata(
        caption=payload.caption, hashtags=payload.hashtags, cover_slide=0
    )

    if payload.schedule_at:
        save_scheduled_post(
            carousel_id=payload.carousel_id,
            caption=payload.caption,
            hashtags=payload.hashtags,
            schedule_at=payload.schedule_at,
            db_path=_db_path(),
        )
        return {"media_id": None, "feed_url": "", "status": "queued",
                "provider": get_publisher().provider}

    result = get_publisher().publish(carousel, metadata, output_dir)
    save_published_post(
        provider=result.provider,
        media_id=result.media_id,
        carousel_id=payload.carousel_id,
        caption=payload.caption,
        hashtags=payload.hashtags,
        feed_url=result.feed_url,
        db_path=_db_path(),
    )
    return {"media_id": result.media_id, "feed_url": result.feed_url,
            "status": result.status, "provider": result.provider}


@router.get("/posts")
def posts() -> list[dict]:
    return list_published_posts(db_path=_db_path())


@router.get("/status")
def status() -> dict:
    return {
        "provider": get_publisher().provider,
        "oauth_connected": is_oauth_connected(db_path=_db_path()),
        "posts_published": len(list_published_posts(db_path=_db_path())),
    }


@router.post("/oauth/connect")
def oauth_connect() -> dict:
    return save_oauth_token(db_path=_db_path())


@router.post("/oauth/revoke")
def oauth_revoke() -> dict:
    clear_oauth_token(db_path=_db_path())
    return {"status": "revoked", "connected": False}


def _run_scheduler(interval: float = 5.0) -> None:
    """Background thread: publish any scheduled posts whose time has come."""
    while True:
        try:
            for due in due_scheduled_posts(db_path=_db_path()):
                payload = PublishRequest(
                    carousel_id=due["carousel_id"],
                    caption=due["caption"] or "",
                    hashtags=json.loads(due["hashtags"] or "[]"),
                    schedule_at=None,
                )
                try:
                    publish(payload)
                finally:
                    delete_scheduled_post(due["id"], db_path=_db_path())
        except Exception:
            pass
        time.sleep(interval)


def start_scheduler() -> None:
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started:
            return
        init_publisher_db(_db_path())
        _scheduler_started = True
        threading.Thread(target=_run_scheduler, daemon=True).start()
