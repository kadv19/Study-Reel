"""API client helpers for communicating with the StudyReel FastAPI backend."""

from __future__ import annotations

import requests


# ---------------------------------------------------------------------------
# v1 helpers
# ---------------------------------------------------------------------------


def check_backend_health(base_url: str) -> bool:
    """Check whether the StudyReel backend is responsive."""
    try:
        res = requests.get(f"{base_url}/api/v1/health", timeout=2)
        return res.status_code == 200
    except Exception:
        return False


def fetch_pipeline_status(base_url: str) -> dict:
    """Fetch current pipeline state machine telemetry."""
    try:
        res = requests.get(f"{base_url}/api/v1/status", timeout=2)
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}


def upload_syllabus_pdf(base_url: str, filename: str, content: bytes) -> dict:
    """Upload syllabus PDF to backend ingestion endpoint."""
    files = {"file": (filename, content, "application/pdf")}
    res = requests.post(f"{base_url}/api/v1/syllabus/upload", files=files, timeout=30)
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(f"Upload failed with status {res.status_code}: {res.text}")


def fetch_module_topics(base_url: str, module_number: int) -> list[dict]:
    """Generate AI micro-topics for a stored module via the Gemini engine."""
    res = requests.get(
        f"{base_url}/api/v1/modules/{module_number}/topics", timeout=180
    )
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(
        f"Generation failed with status {res.status_code}: {res.text[:200]}"
    )


def render_carousel(base_url: str, module_name: str, topics: list[dict]) -> dict:
    """Render approved topics into 1080x1350 PNG slides; returns carousel info."""
    payload = {"module_name": module_name, "topics": topics}
    res = requests.post(f"{base_url}/api/v1/carousels/render", json=payload, timeout=300)
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(f"Render failed with status {res.status_code}: {res.text[:200]}")


def export_carousel_zip(base_url: str, carousel_id: int) -> bytes:
    """Download the rendered carousel as a ZIP archive of PNG slides."""
    res = requests.get(f"{base_url}/api/v1/carousels/{carousel_id}/export", timeout=60)
    if res.status_code == 200:
        return res.content
    raise RuntimeError(f"Export failed with status {res.status_code}: {res.text[:200]}")


# ---------------------------------------------------------------------------
# v2 helpers  (Phase 2 — Publish Queue)
# ---------------------------------------------------------------------------


def publish_carousel(
    base_url: str,
    carousel_id: int,
    caption: str,
    hashtags: list[str],
    schedule_at: str | None = None,
) -> dict:
    """POST /api/v2/publish — queue or immediately publish a rendered carousel.

    Returns dict with keys: media_id, feed_url, status ('queued'|'published'), provider.
    """
    payload: dict = {
        "carousel_id": carousel_id,
        "caption": caption,
        "hashtags": hashtags,
        "schedule_at": schedule_at,
    }
    res = requests.post(f"{base_url}/api/v2/publish", json=payload, timeout=30)
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(f"Publish failed [{res.status_code}]: {res.text[:200]}")


def fetch_published_posts(base_url: str) -> list[dict]:
    """GET /api/v2/posts — list all published/queued posts (newest first).

    Each item has: id, provider, media_id, carousel_id, caption,
    hashtags, feed_url, published_at.
    """
    try:
        res = requests.get(f"{base_url}/api/v2/posts", timeout=5)
        return res.json() if res.status_code == 200 else []
    except Exception:
        return []


def fetch_v2_status(base_url: str) -> dict:
    """GET /api/v2/status — publisher health: provider, oauth_connected, posts_published."""
    try:
        res = requests.get(f"{base_url}/api/v2/status", timeout=2)
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}


def connect_oauth(base_url: str) -> dict:
    """POST /api/v2/oauth/connect — simulated OAuth handshake.

    Returns dict with keys: token, expires_at (ISO datetime string).
    """
    res = requests.post(f"{base_url}/api/v2/oauth/connect", timeout=5)
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(f"OAuth connect failed [{res.status_code}]: {res.text[:200]}")


def revoke_oauth(base_url: str) -> dict:
    """POST /api/v2/oauth/revoke — revoke the simulated OAuth token.

    Returns dict with keys: status ('revoked'), connected (False).
    """
    res = requests.post(f"{base_url}/api/v2/oauth/revoke", timeout=5)
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(f"OAuth revoke failed [{res.status_code}]: {res.text[:200]}")

