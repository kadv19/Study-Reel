"""One-time migration from instaclone/data/posts.json to PostgreSQL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
BACKEND_DIR = REPO_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.storage.cloudinary_client import upload_image

try:
    from instaclone.posts_store import init_posts_db, is_cloudinary_url, upsert_post
except ModuleNotFoundError:
    from posts_store import init_posts_db, is_cloudinary_url, upsert_post

DATA_DIR = BASE_DIR / "data"
POSTS_FILE = DATA_DIR / "posts.json"


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for env_file in (BASE_DIR / ".env", BACKEND_DIR / ".env"):
        if env_file.exists():
            load_dotenv(env_file)


def _resolve_local(image_path: str, data_dir: Path = DATA_DIR) -> Path:
    if image_path.startswith("/slides/"):
        return data_dir / "slides" / image_path[len("/slides/") :]
    path = Path(image_path)
    if path.is_absolute():
        return path
    data_path = data_dir / path
    if data_path.exists():
        return data_path
    return REPO_DIR / path


def migrate_posts(
    posts: list[dict],
    data_dir: Path = DATA_DIR,
    *,
    upload=upload_image,
    allow_missing: bool = False,
    dry_run: bool = False,
    table: str | None = None,
) -> dict:
    migrated = 0
    skipped: list[dict] = []
    missing: list[dict] = []

    for post in posts:
        post_id = str(post.get("post_id") or "").strip()
        if not post_id:
            skipped.append({"post_id": "", "reason": "missing post_id"})
            continue

        resolved: list[tuple[dict, Path | None]] = []
        post_missing = []
        for slide in post.get("slides") or []:
            image_path = str(slide.get("image_path") or "")
            if is_cloudinary_url(image_path):
                resolved.append((slide, None))
                continue
            local_path = _resolve_local(image_path, data_dir)
            if local_path.exists():
                resolved.append((slide, local_path))
            else:
                post_missing.append(image_path)

        if post_missing:
            missing.append({"post_id": post_id, "paths": post_missing})
            if not allow_missing:
                raise FileNotFoundError(
                    f"{post_id}: missing local slides: {', '.join(post_missing)}"
                )
            skipped.append({"post_id": post_id, "reason": "missing local slides"})
            continue

        if dry_run:
            migrated += 1
            continue

        slides = []
        for index, (slide, local_path) in enumerate(resolved, start=1):
            image_path = str(slide.get("image_path") or "")
            if local_path is not None:
                public_id = f"studyreel/{post_id}/slide_{index:02d}"
                image_path = upload(local_path, public_id)
                if not image_path.startswith("https://res.cloudinary.com/"):
                    raise RuntimeError(
                        f"{post_id}: Cloudinary upload failed for {local_path}"
                    )
            slides.append(
                {
                    "slide_number": slide.get("slide_number", index),
                    "image_path": image_path,
                    "header": slide.get("header", ""),
                }
            )

        upsert_post(
            {
                "post_id": post_id,
                "media_id": post.get("media_id") or post_id,
                "slides": slides,
                "caption": post.get("caption") or "",
                "hashtags": post.get("hashtags") or [],
                "cover_slide": post.get("cover_slide") or 0,
                "likes": post.get("likes") or 0,
                "views": post.get("views") or 0,
                "created_at": post.get("created_at"),
            },
            table=table,
        )
        migrated += 1

    return {
        "migrated": migrated,
        "skipped": skipped,
        "missing": missing,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--posts-file", type=Path, default=POSTS_FILE)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--table", default=None)
    parser.add_argument("--skip-missing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    _load_env()
    posts = json.loads(args.posts_file.read_text(encoding="utf-8"))
    if not args.dry_run:
        init_posts_db(args.table)

    result = migrate_posts(
        posts,
        args.data_dir,
        allow_missing=args.skip_missing,
        dry_run=args.dry_run,
        table=args.table,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
