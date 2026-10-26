import pytest

from instaclone import posts_store
from instaclone.migrate_posts import migrate_posts

CLOUDINARY_SLIDE = "https://res.cloudinary.com/demo/image/upload/existing.png"


def _slide(tmp_path, post_id, name):
    path = tmp_path / "slides" / post_id / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"png")
    return f"/slides/{post_id}/{name}"


def test_migrate_posts_preserves_counts_and_media_id(tmp_path, isolated_posts_table):
    first = _slide(tmp_path, "legacy_1", "slide_01.png")
    second = _slide(tmp_path, "legacy_1", "slide_02.png")
    uploads = []

    def fake_upload(path, public_id):
        uploads.append((path, public_id))
        return f"https://res.cloudinary.com/demo/image/upload/{public_id}.png"

    posts = [
        {
            "post_id": "legacy_1",
            "media_id": "legacy_media",
            "slides": [
                {"slide_number": 1, "image_path": first, "header": "One"},
                {"slide_number": 2, "image_path": second, "header": "Two"},
                {"slide_number": 3, "image_path": CLOUDINARY_SLIDE, "header": "Three"},
            ],
            "caption": "Legacy",
            "hashtags": ["#legacy"],
            "cover_slide": 1,
            "likes": 12,
            "views": 34,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    ]

    result = migrate_posts(
        posts, tmp_path, upload=fake_upload, table=isolated_posts_table
    )
    assert result["migrated"] == 1
    assert len(uploads) == 2

    post = posts_store.get_post("legacy_media", table=isolated_posts_table)
    assert post["post_id"] == "legacy_1"
    assert post["media_id"] == "legacy_media"
    assert post["likes"] == 12
    assert post["views"] == 34
    assert post["created_at"] == "2026-01-01T00:00:00+00:00"
    assert [s["image_path"] for s in post["slides"]] == [
        "https://res.cloudinary.com/demo/image/upload/studyreel/legacy_1/slide_01.png",
        "https://res.cloudinary.com/demo/image/upload/studyreel/legacy_1/slide_02.png",
        CLOUDINARY_SLIDE,
    ]


def test_migrate_posts_is_idempotent(tmp_path, isolated_posts_table):
    local = _slide(tmp_path, "legacy_2", "slide_01.png")

    def fake_upload(path, public_id):
        return f"https://res.cloudinary.com/demo/image/upload/{public_id}.png"

    posts = [
        {
            "post_id": "legacy_2",
            "slides": [{"slide_number": 1, "image_path": local, "header": "One"}],
            "likes": 7,
            "views": 9,
            "created_at": "2026-01-02T00:00:00+00:00",
        }
    ]

    migrate_posts(posts, tmp_path, upload=fake_upload, table=isolated_posts_table)
    posts[0]["caption"] = "Updated"
    migrate_posts(posts, tmp_path, upload=fake_upload, table=isolated_posts_table)

    post = posts_store.get_post("legacy_2", table=isolated_posts_table)
    assert post["caption"] == "Updated"
    assert post["likes"] == 7
    assert post["views"] == 9


def test_migrate_posts_reports_missing_slides(tmp_path, isolated_posts_table):
    posts = [
        {
            "post_id": "missing_post",
            "slides": [{"slide_number": 1, "image_path": "/slides/missing/slide_01.png"}],
        }
    ]

    with pytest.raises(FileNotFoundError):
        migrate_posts(posts, tmp_path, table=isolated_posts_table)

    result = migrate_posts(
        posts, tmp_path, allow_missing=True, table=isolated_posts_table
    )
    assert result["migrated"] == 0
    assert result["missing"][0]["post_id"] == "missing_post"
    assert result["skipped"][0]["reason"] == "missing local slides"
