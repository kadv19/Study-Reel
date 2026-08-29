import os

from app.publisher.instaclone import InstaClonePublisher
from app.publisher.instagram import InstagramGraphAPIPublisher
from app.publisher.publisher import Publisher, PublishResult

__all__ = ["Publisher", "PublishResult", "get_publisher"]


def get_publisher() -> Publisher:
    """Select the active delivery target from the PUBLISHER env var.

    `instaclone` (default) -> local mini-Instagram. `instagram` -> real Meta
    Graph API (Phase 3). The pipeline never changes; only this switch does.
    """
    name = os.getenv("PUBLISHER", "instaclone").lower()
    if name == "instagram":
        return InstagramGraphAPIPublisher()
    return InstaClonePublisher(os.getenv("INSTACLONE_URL", "http://127.0.0.1:8100"))
