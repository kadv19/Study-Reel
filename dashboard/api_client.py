"""API client helpers for communicating with the StudyReel FastAPI backend.

Phase 1 (v1) helpers handle ingestion, generation, rendering and export.
Phase 2 (v2) helpers handle the publish pipeline: OAuth handshake, publish,
scheduled posts and the published-posts ledger.
"""

import requests


# ----------------------------- Phase 1 (v1) ---------------------------------


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
    # dashboard upload now sends a fixed owner header so the privacy filter keeps it visible to the dashboard pseudo-user
    headers = {"X-User-Id": "dashboard"}
    res = requests.post(f"{base_url}/api/v1/syllabus/upload", files=files, headers=headers, timeout=30)
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


# ----------------------------- Phase 2 (v2) ---------------------------------


def fetch_v2_status(base_url: str) -> dict:
    """Publisher health: provider, OAuth connection, posts published count."""
    try:
        res = requests.get(f"{base_url}/api/v2/status", timeout=5)
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}


def connect_oauth(base_url: str) -> dict:
    """Simulated OAuth handshake -> returns {token, expires_at}."""
    res = requests.post(f"{base_url}/api/v2/oauth/connect", timeout=10)
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(f"OAuth connect failed: {res.status_code} {res.text[:200]}")


def revoke_oauth(base_url: str) -> dict:
    """Revoke the simulated OAuth token."""
    res = requests.post(f"{base_url}/api/v2/oauth/revoke", timeout=10)
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(f"OAuth revoke failed: {res.status_code} {res.text[:200]}")


def publish_carousel(
    base_url: str,
    carousel_id: int,
    caption: str,
    hashtags: list[str],
    cover_slide: int = 0,
    schedule_at: str | None = None,
) -> dict:
    """Publish (or schedule) a rendered carousel to the active publisher."""
    payload = {
        "carousel_id": carousel_id,
        "caption": caption,
        "hashtags": hashtags,
        "cover_slide": cover_slide,
        "schedule_at": schedule_at,
    }
    res = requests.post(f"{base_url}/api/v2/publish", json=payload, timeout=60)
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(f"Publish failed: {res.status_code} {res.text[:200]}")


def generate_tailored_metadata(base_url: str, module_name: str, topics: list[dict]) -> dict:
    """Call tailored preview — returns {caption, hashtags, cover_slide}."""
    res = requests.post(f"{base_url}/api/v2/metadata/preview", json={"module_name": module_name, "topics": topics}, timeout=60)
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(f"Tailored preview failed: {res.status_code} {res.text[:200]}")


def fetch_published_posts(base_url: str) -> list[dict]:
    """List published/queued posts from the publisher ledger."""
    try:
        res = requests.get(f"{base_url}/api/v2/posts", timeout=10)
        return res.json() if res.status_code == 200 else []
    except Exception:
        return []
