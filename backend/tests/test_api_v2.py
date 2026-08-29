"""Tests for the Phase 2 v2 publish API (InstaClone + scheduler mocked)."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.publisher.store import init_publisher_db
from app.schemas import Carousel, MicroTopic, Slide


@pytest.fixture
def client_ctx():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fake_publisher(monkeypatch):
    """Patch get_publisher() so routes don't hit a real InstaClone app."""
    published = []

    class _Fake:
        provider = "instaclone"

        def publish(self, carousel, metadata, output_dir):
            from app.publisher.publisher import PublishResult
            published.append((carousel, metadata))
            return PublishResult(
                media_id="m1", feed_url="http://127.0.0.1:8100/feed", status="published", provider="instaclone"
            )

        def list_posts(self):
            return []

        def get_post(self, media_id):
            return None

    fp = _Fake()
    monkeypatch.setattr("app.api_v2.get_publisher", lambda: fp)
    return fp, published


def test_oauth_connect_and_status(client_ctx, tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLISHER_DB", str(tmp_path / "pub.db"))
    init_publisher_db(str(tmp_path / "pub.db"))
    r = client_ctx.post("/api/v2/oauth/connect")
    assert r.status_code == 200
    body = r.json()
    assert body["token"] and body["expires_at"]
    assert client_ctx.get("/api/v2/status").json()["oauth_connected"] is True
    rr = client_ctx.post("/api/v2/oauth/revoke")
    assert rr.json()["connected"] is False


def test_publish_requires_rendered_carousel(client_ctx, monkeypatch, tmp_path, fake_publisher):
    monkeypatch.setenv("PUBLISHER_DB", str(tmp_path / "pub.db"))
    init_publisher_db(str(tmp_path / "pub.db"))
    # No carousel with id 999 exists -> 404
    r = client_ctx.post("/api/v2/publish", json={"carousel_id": 999, "caption": "x", "hashtags": ["#a", "#b", "#c"]})
    assert r.status_code == 404


def test_publish_end_to_end(client_ctx, monkeypatch, tmp_path, fake_publisher):
    from app.db.database import save_carousel
    monkeypatch.setenv("PUBLISHER_DB", str(tmp_path / "pub.db"))
    init_publisher_db(str(tmp_path / "pub.db"))

    # Render a real carousel so a DB row + PNGs exist
    from app.renderer.render import render_carousel
    topics = [MicroTopic(header="Topic A", body="Body.", language_tag=None)]
    slides = [Slide(slide_type="text", index=0, topic=topics[0])]
    carousel = Carousel(carousel_id="abc123", module_name="Module 1", slides=slides)
    out = tmp_path / "renders" / "abc123"
    render_carousel(carousel, out_dir=out)
    cid = save_carousel(carousel, module_id=1, output_dir=str(out))

    r = client_ctx.post(
        "/api/v2/publish",
        json={"carousel_id": cid, "caption": "Learn Topic A! #VTU #CSE", "hashtags": ["#vt", "#cse", "#x"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "published"
    assert body["provider"] == "instaclone"
    assert fake_publisher[1]  # publish() was invoked
    # Listed in posts
    posts = client_ctx.get("/api/v2/posts").json()
    assert len(posts) == 1
    assert posts[0]["media_id"] == "m1"
