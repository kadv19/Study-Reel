"""MINIMAL InstaClone stub — P3 OWNS instaclone/, this is a temporary
contract-satisfying placeholder so the Phase 2 publish pipeline is demoable
end-to-end BEFORE the full feed UI lands. P3 should replace app.py + feed.html
with the real dark, swipeable Instagram-style experience.

Contract (stable — do not change without telling P1):
  POST /api/posts           {"post_id","slides":[{"slide_number","image_path","header"}],"caption","hashtags","cover_slide"}
                          -> 200 {"media_id","feed_url"}
  POST /api/posts/{id}/interact  {"action":"like"|"view"} -> 200 {"likes","views"}
  GET  /api/feed           -> {"posts":[...]}
  GET  /feed               -> dark feed page
  GET  /slides/{post_id}/{file} -> PNG (static)
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

DATA_DIR = Path(__file__).resolve().parent / "data"
SLIDES_DIR = DATA_DIR / "slides"
DATA_DIR.mkdir(exist_ok=True)
SLIDES_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="InstaClone (stub)")
app.mount("/slides", StaticFiles(directory=str(SLIDES_DIR)), name="slides")

POSTS: dict[str, dict] = {}


@app.post("/api/posts")
async def create_post(payload: Request):
    body = await payload.json()
    post_id = body.get("post_id") or uuid.uuid4().hex[:8]
    post = {
        "media_id": post_id,
        "post_id": post_id,
        "caption": body.get("caption", ""),
        "hashtags": body.get("hashtags", []),
        "cover_slide": body.get("cover_slide", 0),
        "slides": body.get("slides", []),
        "likes": 0,
        "views": 0,
    }
    POSTS[post_id] = post
    return {"media_id": post_id, "feed_url": f"http://127.0.0.1:8100/feed#${post_id}"}


@app.post("/api/posts/{post_id}/interact")
async def interact(post_id: str, payload: Request):
    if post_id not in POSTS:
        raise HTTPException(404, "post not found")
    body = await payload.json()
    if body.get("action") == "like":
        POSTS[post_id]["likes"] += 1
    elif body.get("action") == "view":
        POSTS[post_id]["views"] += 1
    return {"likes": POSTS[post_id]["likes"], "views": POSTS[post_id]["views"]}


@app.get("/api/feed")
def feed():
    ordered = sorted(POSTS.values(), key=lambda p: p["post_id"], reverse=True)
    return {"posts": ordered}


@app.get("/feed", response_class=HTMLResponse)
def feed_page():
    cards = []
    for p in sorted(POSTS.values(), key=lambda p: p["post_id"], reverse=True):
        slides = "".join(
            f'<img src="{s["image_path"]}" style="width:200px;border-radius:12px;margin:4px">'
            for s in p["slides"]
        )
        tags = " ".join(f"<span style='color:#60A5FA'>#{t}</span>" for t in p["hashtags"])
        cards.append(
            f"<div style='background:#182234;border:1px solid #3B82F6;border-radius:12px;"
            f"padding:16px;margin:12px;width:480px'>"
            f"<h3 style='color:#fff'>{p['caption'] or '(no caption)'}</h3>{slides}"
            f"<p style='color:#94A3B8'>{tags}</p>"
            f"<p style='color:#94A3B8'>❤️ {p['likes']} · 👁 {p['views']}</p></div>"
        )
    return (
        "<html><head><style>body{background:#0F172A;font-family:sans-serif}"
        "</style></head><body>"
        f"<h1 style='color:#60A5FA'>🎬 StudyReel InstaClone</h1>"
        f"{''.join(cards) or '<p style=\"color:#94A3B8\">No posts yet.</p>'}"
        "</body></html>"
    )
