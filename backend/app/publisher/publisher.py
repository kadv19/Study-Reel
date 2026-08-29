"""Publisher abstraction — the single seam between the pipeline and a
delivery target. Phase 2 ships InstaClonePublisher (local mini-Instagram);
Phase 3 drops in InstagramGraphAPIPublisher (real Meta API) with no pipeline
changes — just flip PUBLISHER in .env.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from app.schemas import Carousel, PostMetadata


@dataclass
class PublishResult:
    media_id: str
    feed_url: str
    status: str          # "published" | "queued"
    provider: str


@runtime_checkable
class Publisher(Protocol):
    provider: str

    def publish(
        self, carousel: Carousel, metadata: PostMetadata, output_dir: Path
    ) -> PublishResult:
        """Render-backed carousel -> delivered post on the target platform."""
        ...

    def list_posts(self) -> list[dict]:
        """Most-recent-first list of delivered posts (with like/view counts)."""
        ...

    def get_post(self, media_id: str) -> Optional[dict]:
        """Single post by id, or None."""
        ...
