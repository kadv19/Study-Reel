"""Tests for the Phase 2 Publisher abstraction + store layer (no live InstaClone)."""

import json

import pytest

from app.publisher import get_publisher
from app.publisher.publisher import PublishResult
from app.publisher.store import (
    clear_oauth_token,
    init_publisher_db,
    is_oauth_connected,
    save_oauth_token,
    save_published_post,
)
from app.schemas import Carousel, MicroTopic, Slide


def _sample_carousel(n=3):
    slides = [
        Slide(slide_type="text" if i % 2 == 0 else "mixed", index=i,
              topic=MicroTopic(header=f"Topic {i}", body="Body text.", language_tag=None))
        for i in range(n)
    ]
    return Carousel(carousel_id="abc123", module_name="Module 1", slides=slides)


def test_get_publisher_defaults_to_instaclone(monkeypatch):
    monkeypatch.delenv("PUBLISHER", raising=False)
    p = get_publisher()
    assert p.provider == "instaclone"


def test_get_publisher_instagram_constructs(monkeypatch):
    monkeypatch.setenv("PUBLISHER", "instagram")
    monkeypatch.setenv("IG_USER_ID", "123")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "tok")
    from app.publisher.instagram import InstagramGraphAPIPublisher
    p = get_publisher()
    assert isinstance(p, InstagramGraphAPIPublisher)
    assert p.provider == "instagram"


class _FakePublisher:
    provider = "fake"

    def __init__(self):
        self.calls = []

    def publish(self, carousel, metadata, output_dir):
        self.calls.append((carousel, metadata, output_dir))
        return PublishResult(media_id="m1", feed_url="http://x/feed", status="published", provider="fake")

    def list_posts(self):
        return []

    def get_post(self, media_id):
        return None


def test_publisher_store_roundtrip(tmp_path):
    db = tmp_path / "pub.db"
    init_publisher_db(db)
    save_published_post("instaclone", "m1", 7, "cap", ["#a", "#b"], "http://x", db_path=db)
    from app.publisher.store import list_published_posts
    rows = list_published_posts(db)
    assert len(rows) == 1
    assert rows[0]["media_id"] == "m1"
    assert json.loads(rows[0]["hashtags"]) == ["#a", "#b"]


def test_oauth_simulated_lifecycle(tmp_path):
    db = tmp_path / "pub.db"
    init_publisher_db(db)
    assert is_oauth_connected(db) is False
    tok = save_oauth_token(db)
    assert is_oauth_connected(db) is True
    assert tok["token"]
    clear_oauth_token(db)
    assert is_oauth_connected(db) is False
