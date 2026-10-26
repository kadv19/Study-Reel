"""API client helpers for communicating with the StudyReel FastAPI backend.

Phase 1 (v1) helpers handle ingestion, generation, rendering and export.
Phase 2 (v2) helpers handle the publish pipeline: OAuth handshake, publish,
scheduled posts and the published-posts ledger.

Authentication: every request carries the session bearer token from
STUDYREEL_TOKEN (or set_token()). Operator-only /api/v2 routes additionally
carry the X-Admin-Key header from ADMIN_API_KEY (or set_admin_key()).
"""

import os

import requests

_token: str | None = None
_admin_key: str | None = None


def set_token(token: str | None) -> None:
    """Set the bearer token used for subsequent requests."""
    global _token
    _token = token


def set_admin_key(key: str | None) -> None:
    """Set the operator key used for /api/v2 requests."""
    global _admin_key
    _admin_key = key


def _get_token() -> str | None:
    return _token or os.getenv("STUDYREEL_TOKEN") or os.getenv("SR_SESSION_TOKEN")


def _get_admin_key() -> str | None:
    return _admin_key or os.getenv("ADMIN_API_KEY")


def _auth_headers() -> dict:
    token = _get_token()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _v2_headers() -> dict:
    headers = _auth_headers()
    admin_key = _get_admin_key()
    if admin_key:
        headers["X-Admin-Key"] = admin_key
    return headers


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
        res = requests.get(f"{base_url}/api/v1/status", headers=_auth_headers(), timeout=2)
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}


def upload_syllabus_pdf(base_url: str, filename: str, content: bytes) -> dict:
    """Upload syllabus PDF to backend ingestion endpoint."""
    files = {"file": (filename, content, "application/pdf")}
    res = requests.post(
        f"{base_url}/api/v1/syllabus/upload",
        files=files,
        headers=_auth_headers(),
        timeout=30,
    )
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(f"Upload failed with status {res.status_code}: {res.text}")


def fetch_module_topics(base_url: str, module_number: int) -> list[dict]:
    """Generate AI micro-topics for a stored module via the Gemini engine."""
    res = requests.get(
        f"{base_url}/api/v1/modules/{module_number}/topics",
        headers=_auth_headers(),
        timeout=180,
    )
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(
        f"Generation failed with status {res.status_code}: {res.text[:200]}"
    )


def render_carousel(base_url: str, module_name: str, topics: list[dict]) -> dict:
    """Render approved topics into 1080x1350 PNG slides; returns carousel info."""
    payload = {"module_name": module_name, "topics": topics}
    res = requests.post(
        f"{base_url}/api/v1/carousels/render",
        json=payload,
        headers=_auth_headers(),
        timeout=300,
    )
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(f"Render failed with status {res.status_code}: {res.text[:200]}")


def export_carousel_zip(base_url: str, carousel_id: int) -> bytes:
    """Download the rendered carousel as a ZIP archive of PNG slides."""
    res = requests.get(
        f"{base_url}/api/v1/carousels/{carousel_id}/export",
        headers=_auth_headers(),
        timeout=60,
    )
    if res.status_code == 200:
        return res.content
    raise RuntimeError(f"Export failed with status {res.status_code}: {res.text[:200]}")


# ----------------------------- Phase 2 (v2) ---------------------------------


def fetch_v2_status(base_url: str) -> dict:
    """Publisher health: provider, OAuth connection, posts published count."""
    try:
        res = requests.get(f"{base_url}/api/v2/status", headers=_v2_headers(), timeout=5)
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}


def connect_oauth(base_url: str) -> dict:
    """Simulated OAuth handshake -> returns {token, expires_at}."""
    res = requests.post(f"{base_url}/api/v2/oauth/connect", headers=_v2_headers(), timeout=10)
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(f"OAuth connect failed: {res.status_code} {res.text[:200]}")


def revoke_oauth(base_url: str) -> dict:
    """Revoke the simulated OAuth token."""
    res = requests.post(f"{base_url}/api/v2/oauth/revoke", headers=_v2_headers(), timeout=10)
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
    res = requests.post(
        f"{base_url}/api/v2/publish",
        json=payload,
        headers=_v2_headers(),
        timeout=60,
    )
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(f"Publish failed: {res.status_code} {res.text[:200]}")


def generate_tailored_metadata(base_url: str, module_name: str, topics: list[dict]) -> dict:
    """Call tailored preview — returns {caption, hashtags, cover_slide}."""
    res = requests.post(
        f"{base_url}/api/v2/metadata/preview",
        json={"module_name": module_name, "topics": topics},
        headers=_v2_headers(),
        timeout=60,
    )
    if res.status_code == 200:
        return res.json()
    raise RuntimeError(f"Tailored preview failed: {res.status_code} {res.text[:200]}")


def fetch_published_posts(base_url: str) -> list[dict]:
    """List published/queued posts from the publisher ledger."""
    try:
        res = requests.get(f"{base_url}/api/v2/posts", headers=_v2_headers(), timeout=10)
        return res.json() if res.status_code == 200 else []
    except Exception:
        return []
