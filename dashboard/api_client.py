"""API client helpers for communicating with the StudyReel FastAPI backend."""

import requests


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
