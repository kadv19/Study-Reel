"""API unit tests for InstaClone standalone application."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from instaclone.app import app, DATA_FILE, load_posts, save_posts


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Isolate JSON storage to a temporary file for clean testing."""
    test_data_file = tmp_path / "test_posts.json"
    test_data_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr("instaclone.app.DATA_FILE", test_data_file)
    yield test_data_file


@pytest.fixture
def client():
    return TestClient(app)


def test_create_post_contract(client):
    payload = {
        "post_id": "test_post_001",
        "slides": [
            {"slide_number": 1, "image_path": "demo_output/slide_01.png", "header": "Intro"},
            {"slide_number": 2, "image_path": "demo_output/slide_02.png", "header": "Code"},
        ],
        "caption": "Python async generator patterns in-depth #python #async",
        "hashtags": ["#python", "#async", "#studyreel"],
        "cover_slide": 1,
    }
    response = client.post("/api/posts", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["media_id"] == "test_post_001"
    assert "/feed" in data["feed_url"]


def test_interact_like_and_view(client):
    post_payload = {
        "post_id": "post_interact_test",
        "slides": [{"slide_number": 1, "image_path": "demo_output/slide_01.png", "header": "Slide 1"}],
        "caption": "Testing interactions",
        "hashtags": ["#test"],
        "cover_slide": 1,
    }
    client.post("/api/posts", json=post_payload)

    # Test like
    like_res = client.post("/api/posts/post_interact_test/interact", json={"action": "like"})
    assert like_res.status_code == 200
    assert like_res.json() == {"likes": 1, "views": 0}

    # Test view
    view_res = client.post("/api/posts/post_interact_test/interact", json={"action": "view"})
    assert view_res.status_code == 200
    assert view_res.json() == {"likes": 1, "views": 1}

    # Test second like
    like_res_2 = client.post("/api/posts/post_interact_test/interact", json={"action": "like"})
    assert like_res_2.status_code == 200
    assert like_res_2.json() == {"likes": 2, "views": 1}


def test_feed_ordering_and_counts(client):
    client.post("/api/posts", json={
        "post_id": "post_first",
        "slides": [{"slide_number": 1, "image_path": "slide_01.png", "header": "First"}],
        "caption": "First Post",
        "hashtags": ["#first"],
        "cover_slide": 1,
    })
    client.post("/api/posts", json={
        "post_id": "post_second",
        "slides": [{"slide_number": 1, "image_path": "slide_02.png", "header": "Second"}],
        "caption": "Second Post",
        "hashtags": ["#second"],
        "cover_slide": 1,
    })

    client.post("/api/posts/post_first/interact", json={"action": "like"})

    feed_res = client.get("/api/feed")
    assert feed_res.status_code == 200
    feed = feed_res.json()
    assert len(feed) == 2
    # Latest first
    assert feed[0]["post_id"] == "post_second"
    assert feed[1]["post_id"] == "post_first"
    assert feed[1]["likes"] == 1


def test_feed_html_serving(client):
    response = client.get("/feed")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "StudyReel" in response.text
    assert "feed-container" in response.text


def test_interact_error_handling(client):
    # Nonexistent post
    res_404 = client.post("/api/posts/ghost_post/interact", json={"action": "like"})
    assert res_404.status_code == 404

    # Valid post with invalid action
    client.post("/api/posts", json={
        "post_id": "post_valid",
        "slides": [{"slide_number": 1, "image_path": "slide.png", "header": "H"}],
        "caption": "Caption",
        "hashtags": [],
        "cover_slide": 1,
    })
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
