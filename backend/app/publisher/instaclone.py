"""Delivers carousels to the standalone InstaClone app (local mini-Instagram)."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import requests

from app.publisher.publisher import PublishResult
from app.schemas import Carousel, PostMetadata

CLONE_SLIDES_DIR = Path(__file__).resolve().parents[3] / "instaclone" / "data" / "slides"


class InstaClonePublisher:
    provider = "instaclone"

    def __init__(self, base_url: str = "http://127.0.0.1:8100"):
        self.base = base_url.rstrip("/")

    def publish(
        self, carousel: Carousel, metadata: PostMetadata, output_dir: Path
    ) -> PublishResult:
        post_id = uuid.uuid4().hex[:8]
        target = CLONE_SLIDES_DIR / post_id
        target.mkdir(parents=True, exist_ok=True)

        slides = []
        for i, slide in enumerate(carousel.slides):
            fname = f"slide_{i + 1:02d}.png"
            src = Path(output_dir) / fname
            if src.exists():
                shutil.copy(src, target / fname)
            slides.append({
                "slide_number": i + 1,
                "image_path": f"/slides/{post_id}/{fname}",
                "header": slide.topic.header,
            })

        payload = {
            "post_id": post_id,
            "slides": slides,
            "caption": metadata.caption,
            "hashtags": metadata.hashtags,
            "cover_slide": metadata.cover_slide,
        }
        resp = requests.post(f"{self.base}/api/posts", json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return PublishResult(
            media_id=data.get("media_id", post_id),
            feed_url=data.get("feed_url", f"{self.base}/feed"),
            status="published",
            provider=self.provider,
        )

    def list_posts(self) -> list[dict]:
        resp = requests.get(f"{self.base}/api/feed", timeout=10)
        resp.raise_for_status()
        return resp.json().get("posts", [])

    def get_post(self, media_id: str) -> dict | None:
        for post in self.list_posts():
            if post.get("media_id") == media_id or post.get("post_id") == media_id:
                return post
        return None
