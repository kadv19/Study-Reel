"""InstaClone FastAPI server for rendering pipeline feed delivery."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
import httpx
from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "posts.json"
STATIC_DIR = BASE_DIR / "static"
FEED_HTML = BASE_DIR / "feed.html"
DATA_DIR = BASE_DIR / "data"
SLIDES_DIR = DATA_DIR / "slides"

app = FastAPI(title="StudyReel InstaClone", version="0.1.0")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# Publisher copies PNGs to instaclone/data/slides/{post_id}/ and expects /slides/{post_id}/slide_*.png
SLIDES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/slides", StaticFiles(directory=str(SLIDES_DIR)), name="slides")


@app.middleware("http")
async def disable_compression(request, call_next):
    response = await call_next(request)
    response.headers["Content-Encoding"] = "identity"
    return response


class SlideItem(BaseModel):
    slide_number: int = Field(..., ge=1)
    image_path: str = Field(...)
    header: str = Field(default="")


class CreatePostRequest(BaseModel):
    post_id: str
    slides: List[SlideItem]
    caption: str = ""
    hashtags: List[str] = Field(default_factory=list)
    cover_slide: int = Field(default=0, ge=0, description="0-indexed cover slide, matches PostMetadata")


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
    return {"media_id": payload.post_id, "feed_url": f"http://127.0.0.1:8100/feed#{payload.post_id}"}


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
def get_feed(
    sort: str = Query(default="newest", description="trending|newest"),
    tag: Optional[str] = Query(default=None, description="filter by hashtag without #"),
) -> Dict[str, List[Dict[str, Any]]]:
    posts = load_posts()
    if tag:
        t = tag.lower().lstrip("#")
        posts = [p for p in posts if any(h.lower().lstrip("#") == t for h in p.get("hashtags", []))]
    if sort == "newest":
        sorted_posts = sorted(posts, key=lambda p: p.get("created_at", ""), reverse=True)
    else:
        # trending = likes*0.7 + views*0.15 - hours_ago*0.08 (global trending)
        def _score(p: Dict[str, Any]) -> float:
            try:
                created = datetime.fromisoformat(p.get("created_at", "").replace("Z", "+00:00"))
                hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
            except Exception:
                hours = 999
            return p.get("likes", 0) * 0.7 + p.get("views", 0) * 0.15 - hours * 0.08
        sorted_posts = sorted(posts, key=_score, reverse=True)
    return {"posts": sorted_posts}


@app.get("/feed", response_class=HTMLResponse)
def serve_feed() -> HTMLResponse:
    # Card Catalog is primary; old Instagram feed kept at /feed_legacy for cold-start debug only
    if DECK_HTML.exists():
        return HTMLResponse(content=DECK_HTML.read_text(encoding="utf-8"))
    if FEED_HTML.exists():
        return HTMLResponse(content=FEED_HTML.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="feed not found")

@app.get("/feed_legacy", response_class=HTMLResponse)
def serve_feed_legacy() -> HTMLResponse:
    if FEED_HTML.exists():
        return HTMLResponse(content=FEED_HTML.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="feed.html not found")


DECK_HTML = BASE_DIR / "deck.html"
CABINET_HTML = BASE_DIR / "cabinet.html"
UPLOAD_HTML = BASE_DIR / "upload.html"
AUTH_HTML = BASE_DIR / "auth.html"
ONBOARDING_HTML = BASE_DIR / "onboarding.html"

@app.get("/auth", response_class=HTMLResponse)
def serve_auth() -> HTMLResponse:
    if AUTH_HTML.exists():
        return HTMLResponse(content=AUTH_HTML.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="auth.html not found")

@app.get("/onboarding", response_class=HTMLResponse)
def serve_onboarding() -> HTMLResponse:
    if ONBOARDING_HTML.exists():
        return HTMLResponse(content=ONBOARDING_HTML.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="onboarding.html not found")

@app.get("/deck", response_class=HTMLResponse)
def serve_deck() -> HTMLResponse:
    if DECK_HTML.exists():
        return HTMLResponse(content=DECK_HTML.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="deck.html not found")

@app.get("/cabinet", response_class=HTMLResponse)
def serve_cabinet() -> HTMLResponse:
    if CABINET_HTML.exists():
        return HTMLResponse(content=CABINET_HTML.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="cabinet.html not found")

@app.get("/upload", response_class=HTMLResponse)
def serve_upload() -> HTMLResponse:
    if UPLOAD_HTML.exists():
        return HTMLResponse(content=UPLOAD_HTML.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="upload.html not found")

@app.get("/", response_class=HTMLResponse)
def serve_root() -> HTMLResponse:
    # Card Catalog is now primary (deck), old feed kept at /feed for cold-start
    if DECK_HTML.exists():
        return HTMLResponse(content=DECK_HTML.read_text(encoding="utf-8"))
    return HTMLResponse(content=FEED_HTML.read_text(encoding="utf-8") if FEED_HTML.exists() else "<h1>StudyReel</h1>")


@app.get("/config.js")
async def config_js():
    backend_url = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
    js = f"window.STUDYREEL_BACKEND = '{backend_url}';"
    return Response(content=js, media_type="application/javascript")


# ---- Proxy backend API (single tunnel) ------------------------------------
# Any /api/v1/* or /api/v2/* not handled locally is forwarded to backend 8000.
# This collapses two tunnels into one: phone -> instaclone 8100 -> backend 8000.

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")


async def _proxy(request: Request) -> Response:
    url = f"{BACKEND_URL}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    # forward headers except hop-by-hop, force identity so backend never compresses
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length", "connection")}
    headers["Accept-Encoding"] = "identity"
    body = await request.body()
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        resp = await client.request(request.method, url, headers=headers, content=body)
        excluded = {"content-encoding", "content-length", "transfer-encoding", "connection"}
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
        return Response(content=resp.content, status_code=resp.status_code, headers=headers, media_type=resp.headers.get("content-type"))


@app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_v1(path: str, request: Request) -> Response:
    return await _proxy(request)


@app.api_route("/api/v2/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_v2(path: str, request: Request) -> Response:
    return await _proxy(request)


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
