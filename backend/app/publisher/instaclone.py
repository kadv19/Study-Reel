"""Delivers carousels to the standalone InstaClone app (local mini-Instagram)."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import requests

from app.publisher.publisher import PublishResult
from app.schemas import Carousel, PostMetadata
from app.storage.cloudinary_client import upload_image

INSTACLONE_URL = os.environ.get("INSTACLONE_URL", "http://127.0.0.1:8100")


class InstaClonePublisher:
    provider = "instaclone"

    def __init__(self, base_url: str | None = None):
        self.base = (base_url or os.environ.get("INSTACLONE_URL", INSTACLONE_URL)).rstrip("/")

    def publish(
        self, carousel: Carousel, metadata: PostMetadata, output_dir: Path
    ) -> PublishResult:
        post_id = uuid.uuid4().hex[:8]

        # Try to load pre-uploaded Cloudinary URLs persisted by render.py
        cloud_urls: list[str] = []
        try:
            cloud_path = Path(output_dir) / "cloud_urls.json"
            if cloud_path.exists():
                data = json.loads(cloud_path.read_text())
                if isinstance(data, list):
                    cloud_urls = [str(u) if u else "" for u in data]
        except Exception:
            cloud_urls = []

        slides = []
        for i, slide in enumerate(carousel.slides):
            src = Path(output_dir) / f"slide_{i + 1:02d}.png"

            # Prefer Cloudinary URL if available (render-time upload)
            cloud_url = ""
            if i < len(cloud_urls) and cloud_urls[i]:
                cloud_url = cloud_urls[i]
            else:
                public_id = f"studyreel/{carousel.carousel_id}/slide_{i + 1:02d}"
                if src.exists():
                    cloud_url = upload_image(src, public_id)

            if not cloud_url.startswith("https://res.cloudinary.com/"):
                raise RuntimeError(
                    f"Cloudinary upload unavailable for {src}; refusing to publish local slide"
                )
            image_path = cloud_url

            slides.append({
                "slide_number": i + 1,
                "image_path": image_path,
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
