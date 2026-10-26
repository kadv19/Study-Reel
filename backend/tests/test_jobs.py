"""Per-user job isolation, limits, and concurrency tests."""

import threading

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import ExtractedModule, Syllabus


@pytest.fixture(scope="module")
def client_ctx():
    with TestClient(app) as c:
        yield c


def _syllabus(file_name: str = "fake.pdf") -> Syllabus:
    return Syllabus(
        file_name=file_name,
        total_pages=1,
        modules=[
            ExtractedModule(
                module_number=1,
                module_title="Module 1: Networks",
                topic_strings=["OSI model", "TCP/IP basics"],
            )
        ],
    )


def test_concurrent_users_see_only_their_own_job(client_ctx, make_user, monkeypatch):
    entered = threading.Semaphore(0)
    release = threading.Event()

    def fake_process_pdf(path):
        entered.release()
        if not release.wait(10):
            raise RuntimeError("test did not release ingestion")
        return _syllabus()

    monkeypatch.setattr("app.main.process_pdf", fake_process_pdf)

    user_a, headers_a = make_user()
    user_b, headers_b = make_user()
    results = {}
    errors = []

    def upload(key, headers, filename):
        try:
            results[key] = client_ctx.post(
                "/api/v1/syllabus/upload",
                files={"file": (filename, b"%PDF-1.4\n", "application/pdf")},
                headers=headers,
            )
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=upload, args=("a", headers_a, "user-a.pdf")),
        threading.Thread(target=upload, args=("b", headers_b, "user-b.pdf")),
    ]
    for thread in threads:
        thread.start()

    try:
        assert entered.acquire(timeout=30)
        assert entered.acquire(timeout=30)

        status_a = client_ctx.get("/api/v1/status", headers=headers_a).json()
        status_b = client_ctx.get("/api/v1/status", headers=headers_b).json()

        assert status_a["owner_user_id"] == user_a["id"]
        assert status_b["owner_user_id"] == user_b["id"]
        assert "user-a.pdf" in status_a["message"]
        assert "user-b.pdf" in status_b["message"]
        assert status_a["job_id"] != status_b["job_id"]

        cross = client_ctx.get(
            f"/api/v1/status?job_id={status_a['job_id']}", headers=headers_b
        )
        assert cross.status_code == 404
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=30)

    for thread in threads:
        assert not thread.is_alive()

    assert not errors
    assert results["a"].status_code == 200
    assert results["b"].status_code == 200

    done_a = client_ctx.get("/api/v1/status", headers=headers_a).json()
    done_b = client_ctx.get("/api/v1/status", headers=headers_b).json()
    assert done_a["state"] == "DONE"
    assert done_b["state"] == "DONE"
    assert done_a["owner_user_id"] == user_a["id"]
    assert done_b["owner_user_id"] == user_b["id"]


def test_concurrent_same_user_upload_is_rejected(client_ctx, make_user, monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def fake_process_pdf(path):
        entered.set()
        if not release.wait(10):
            raise RuntimeError("test did not release ingestion")
        return _syllabus()

    monkeypatch.setattr("app.main.process_pdf", fake_process_pdf)

    _user, headers = make_user()
    first_result = {}

    def upload():
        first_result["response"] = client_ctx.post(
            "/api/v1/syllabus/upload",
            files={"file": ("first.pdf", b"%PDF-1.4\n", "application/pdf")},
            headers=headers,
        )

    thread = threading.Thread(target=upload)
    thread.start()
    try:
        assert entered.wait(30)

        second = client_ctx.post(
            "/api/v1/syllabus/upload",
            files={"file": ("second.pdf", b"%PDF-1.4\n", "application/pdf")},
            headers=headers,
        )
        assert second.status_code == 429
        assert "active job" in second.json()["detail"]
    finally:
        release.set()
        thread.join(timeout=30)

    assert not thread.is_alive()
    assert first_result["response"].status_code == 200


def test_daily_syllabus_limit(client_ctx, make_user, monkeypatch):
    monkeypatch.setenv("MAX_SYLLABI_PER_USER_PER_DAY", "1")
    monkeypatch.setattr("app.main.process_pdf", lambda path: _syllabus())

    _user, headers = make_user()

    first = client_ctx.post(
        "/api/v1/syllabus/upload",
        files={"file": ("first.pdf", b"%PDF-1.4\n", "application/pdf")},
        headers=headers,
    )
    assert first.status_code == 200

    second = client_ctx.post(
        "/api/v1/syllabus/upload",
        files={"file": ("second.pdf", b"%PDF-1.4\n", "application/pdf")},
        headers=headers,
    )
    assert second.status_code == 429
    assert "Daily limit" in second.json()["detail"]


def test_active_job_limit(client_ctx, make_user):
    from app.db.database import create_job

    user, headers = make_user()
    create_job(user["id"], "generation", "PROCESSING", 0.5, "Working")

    response = client_ctx.post(
        "/api/v1/syllabus/upload",
        files={"file": ("blocked.pdf", b"%PDF-1.4\n", "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 429
    assert "active job" in response.json()["detail"]
