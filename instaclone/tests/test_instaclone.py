"""API unit tests for InstaClone standalone application."""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from instaclone import posts_store
from instaclone.app import app

CLOUDINARY_SLIDE = "https://res.cloudinary.com/demo/image/upload/slide.png"


@pytest.fixture
def client():
    return TestClient(app)


def _post(post_id: str, **overrides):
    payload = {
        "post_id": post_id,
        "slides": [
            {"slide_number": 1, "image_path": CLOUDINARY_SLIDE, "header": "Intro"}
        ],
        "caption": "Caption",
        "hashtags": ["#test"],
        "cover_slide": 0,
    }
    payload.update(overrides)
    return payload


def test_create_post_contract(client):
    response = client.post(
        "/api/posts",
        json=_post(
            "test_post_001",
            slides=[
                {"slide_number": 1, "image_path": CLOUDINARY_SLIDE, "header": "Intro"},
                {"slide_number": 2, "image_path": CLOUDINARY_SLIDE, "header": "Code"},
            ],
            caption="Python async generator patterns in-depth #python #async",
            hashtags=["#python", "#async", "#studyreel"],
            cover_slide=1,
        ),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["media_id"] == "test_post_001"
    assert "/feed" in data["feed_url"]


def test_create_post_rejects_local_slide_paths(client):
    response = client.post(
        "/api/posts",
        json=_post(
            "local_post",
            slides=[
                {"slide_number": 1, "image_path": "/slides/local/slide_01.png", "header": "H"}
            ],
        ),
    )
    assert response.status_code == 400


def test_interact_like_and_view(client):
    client.post("/api/posts", json=_post("post_interact_test"))

    like_res = client.post("/api/posts/post_interact_test/interact", json={"action": "like"})
    assert like_res.status_code == 200
    assert like_res.json() == {"likes": 1, "views": 0}

    view_res = client.post("/api/posts/post_interact_test/interact", json={"action": "view"})
    assert view_res.status_code == 200
    assert view_res.json() == {"likes": 1, "views": 1}

    like_res_2 = client.post("/api/posts/post_interact_test/interact", json={"action": "like"})
    assert like_res_2.status_code == 200
    assert like_res_2.json() == {"likes": 2, "views": 1}


def test_interact_by_media_id(client):
    posts_store.upsert_post(
        {
            "post_id": "canonical_post",
            "media_id": "shared_media",
            "slides": [{"slide_number": 1, "image_path": CLOUDINARY_SLIDE, "header": "H"}],
            "caption": "Caption",
            "hashtags": [],
            "cover_slide": 0,
            "likes": 5,
            "views": 10,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    res = client.post("/api/posts/shared_media/interact", json={"action": "like"})
    assert res.status_code == 200
    assert res.json() == {"likes": 6, "views": 10}


def test_upsert_preserves_interactions(client):
    client.post("/api/posts", json=_post("stable_post"))
    client.post("/api/posts/stable_post/interact", json={"action": "like"})
    client.post("/api/posts/stable_post/interact", json={"action": "view"})

    res = client.post(
        "/api/posts",
        json=_post("stable_post", caption="Updated caption", hashtags=["#updated"]),
    )
    assert res.status_code == 200

    post = posts_store.get_post("stable_post")
    assert post["caption"] == "Updated caption"
    assert post["likes"] == 1
    assert post["views"] == 1


def test_feed_ordering_and_counts(client):
    client.post("/api/posts", json=_post("post_first", hashtags=["#first"]))
    time.sleep(0.01)
    client.post("/api/posts", json=_post("post_second", hashtags=["#second"]))
    client.post("/api/posts/post_first/interact", json={"action": "like"})

    feed_res = client.get("/api/feed")
    assert feed_res.status_code == 200
    data = feed_res.json()
    feed = data if isinstance(data, list) else data.get("posts", [])
    assert len(feed) == 2
    assert feed[0]["post_id"] == "post_second"
    assert feed[1]["post_id"] == "post_first"
    assert feed[1]["likes"] == 1


def test_feed_html_serving(client):
    response = client.get("/feed")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "StudyReel" in response.text
    assert "</html>" in response.text


def test_interact_error_handling(client):
    res_404 = client.post("/api/posts/ghost_post/interact", json={"action": "like"})
    assert res_404.status_code == 404

    client.post("/api/posts", json=_post("post_valid"))
    res_422 = client.post("/api/posts/post_valid/interact", json={"action": "invalid_action"})
    assert res_422.status_code == 422


def test_media_serving(client):
    sample_file = Path("demo_output/slide_01.png")
    if sample_file.exists():
        res = client.get(f"/api/media?path={sample_file.as_posix()}")
        assert res.status_code == 200
        assert "image/" in res.headers.get("content-type", "")

    res_404 = client.get("/api/media?path=nonexistent_image_12345.png")
    assert res_404.status_code == 404


def test_cover_slide_zero_indexed(client):
    payload = _post(
        "cover_zero_test",
        slides=[
            {"slide_number": 1, "image_path": CLOUDINARY_SLIDE, "header": "A"},
            {"slide_number": 2, "image_path": CLOUDINARY_SLIDE, "header": "B"},
        ],
        caption="cover 0",
        cover_slide=0,
    )
    res = client.post("/api/posts", json=payload)
    assert res.status_code == 200
    feed_res = client.get("/api/feed")
    data = feed_res.json()
    feed = data if isinstance(data, list) else data.get("posts", [])
    post = next(p for p in feed if p["post_id"] == "cover_zero_test")
    assert post["cover_slide"] == 0
