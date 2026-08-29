"""Real Meta Instagram Graph API delivery (Phase 3).

This is the swap-in replacement for InstaClonePublisher. It uses the official
flow (create media containers -> publish) but is NOT live-tested in Phase 2 —
it requires a Facebook/Instagram Business account, an app in review, and a
long-lived token. The code below is the real shape; keep it behind the
PUBLISHER=instagram switch and implement token bootstrap (see store.oauth)
before going live.

Reference: https://developers.facebook.com/docs/instagram-api/guides/publishing
"""

from __future__ import annotations

import os
from pathlib import Path

import requests

from app.publisher.publisher import PublishResult
from app.schemas import Carousel, PostMetadata


class InstagramGraphAPIPublisher:
    provider = "instagram"

    def __init__(
        self,
        ig_user_id: str | None = None,
        access_token: str | None = None,
        api_version: str = "v21.0",
    ):
        self.ig_user_id = ig_user_id or os.getenv("IG_USER_ID")
        self.access_token = access_token or os.getenv("IG_ACCESS_TOKEN")
        self.base = f"https://graph.facebook.com/{api_version}/{self.ig_user_id}"
        if not self.ig_user_id or not self.access_token:
            raise RuntimeError(
                "InstagramGraphAPIPublisher needs IG_USER_ID + IG_ACCESS_TOKEN "
                "(Phase 3). Set PUBLISHER=instaclone for the Phase 2 demo."
            )

    def _create_carousel_item(self, image_url: str) -> str:
        """Upload one image as a carousel child container."""
        resp = requests.post(
            f"{self.base}/media",
            data={
                "image_url": image_url,
                "is_carousel_item": "true",
                "access_token": self.access_token,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def publish(
        self, carousel: Carousel, metadata: PostMetadata, output_dir: Path
    ) -> PublishResult:
        child_ids = [self._create_carousel_item(str(output_dir / f"slide_{i + 1:02d}.png"))
                    for i, _ in enumerate(carousel.slides)]
        container = requests.post(
            f"{self.base}/media",
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "caption": f"{metadata.caption}\n\n{' '.join(metadata.hashtags)}",
                "access_token": self.access_token,
            },
            timeout=60,
        )
        container.raise_for_status()
        creation_id = container.json()["id"]

        published = requests.post(
            f"{self.base}/media_publish",
            data={"creation_id": creation_id, "access_token": self.access_token},
            timeout=60,
        )
        published.raise_for_status()
        media_id = published.json()["id"]
        return PublishResult(
            media_id=media_id,
            feed_url=f"https://instagram.com/p/{media_id}",
            status="published",
            provider=self.provider,
        )

    def list_posts(self) -> list[dict]:
        resp = requests.get(
            f"{self.base}/media",
            params={"fields": "id,caption,timestamp", "access_token": self.access_token},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])

    def get_post(self, media_id: str) -> dict | None:
        resp = requests.get(
            f"{self.base}/{media_id}",
            params={"fields": "id,caption", "access_token": self.access_token},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
