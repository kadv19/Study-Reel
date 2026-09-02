"""InstaClone FastAPI server for rendering pipeline feed delivery."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "posts.json"
STATIC_DIR = BASE_DIR / "static"
FEED_HTML = BASE_DIR / "feed.html"

app = FastAPI(title="StudyReel InstaClone", version="0.1.0")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class SlideItem(BaseModel):
    slide_number: int = Field(..., ge=1)
    image_path: str = Field(...)
    header: str = Field(default="")


class CreatePostRequest(BaseModel):
    post_id: str
    slides: List[SlideItem]
    caption: str = ""
    hashtags: List[str] = Field(default_factory=list)
    cover_slide: int = Field(default=1, ge=1)


class InteractRequest(BaseModel):
    action: Literal["like", "view"]


def load_posts() -> List[Dict[str, Any]]:
    if not DATA_FILE.exists():
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text("[]", encoding="utf-8")
        return []
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_posts(posts: List[Dict[str, Any]]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(posts, indent=2), encoding="utf-8")


@app.post("/api/posts", status_code=status.HTTP_200_OK)
def create_post(payload: CreatePostRequest) -> Dict[str, str]:
    posts = load_posts()
    post_dict = payload.model_dump()
    existing_idx = next((i for i, p in enumerate(posts) if p.get("post_id") == payload.post_id), None)
    now_iso = datetime.now(timezone.utc).isoformat()

    if existing_idx is not None:
        existing = posts[existing_idx]
        post_dict["likes"] = existing.get("likes", 0)
        post_dict["views"] = existing.get("views", 0)
        post_dict["created_at"] = existing.get("created_at", now_iso)
        posts[existing_idx] = post_dict
    else:
        post_dict["likes"] = 0
        post_dict["views"] = 0
        post_dict["created_at"] = now_iso
        posts.append(post_dict)

    save_posts(posts)
    return {"media_id": payload.post_id, "feed_url": "/feed"}


@app.post("/api/posts/{media_id}/interact", status_code=status.HTTP_200_OK)
def interact_post(media_id: str, payload: InteractRequest) -> Dict[str, int]:
    posts = load_posts()
    post = next((p for p in posts if p.get("post_id") == media_id or p.get("media_id") == media_id), None)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if payload.action == "like":
        post["likes"] = post.get("likes", 0) + 1
    elif payload.action == "view":
        post["views"] = post.get("views", 0) + 1
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    save_posts(posts)
    return {"likes": post["likes"], "views": post["views"]}


@app.get("/api/feed")
def get_feed() -> List[Dict[str, Any]]:
    posts = load_posts()
    # Sort latest first (descending by created_at or reverse order)
    return sorted(posts, key=lambda p: p.get("created_at", ""), reverse=True)


@app.get("/feed", response_class=HTMLResponse)
def serve_feed() -> HTMLResponse:
    if not FEED_HTML.exists():
        raise HTTPException(status_code=404, detail="feed.html not found")
    return HTMLResponse(content=FEED_HTML.read_text(encoding="utf-8"))


@app.get("/api/media")
def serve_media(path: str = Query(...)) -> FileResponse:
    file_path = Path(path).resolve()
    # Check if relative to workspace root or direct path
    if not file_path.exists():
        candidate = (BASE_DIR.parent / path).resolve()
        if candidate.exists():
            file_path = candidate
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")
    return FileResponse(str(file_path))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8100)
