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
