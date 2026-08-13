"""API tests against the FastAPI app with a real PDF fixture."""

import pytest

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(scope="module")
def client_ctx():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory):
    pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pdf = tmp_path_factory.mktemp("pdfs") / "sample.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.drawString(72, 770, "Module 1: Networks")
    c.drawString(72, 750, "OSI model, TCP/IP basics.")
    c.save()
    return pdf


def test_health(client_ctx):
    r = client_ctx.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_status_defaults_to_idle(client_ctx):
    r = client_ctx.get("/api/v1/status")
    assert r.status_code == 200
    assert r.json()["state"] in {"IDLE", "DONE", "PROCESSING", "FAILED", "NEEDS_SUPERVISION"}


def test_upload_non_pdf_rejected(client_ctx):
    r = client_ctx.post("/api/v1/syllabus/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_upload_pdf_runs_ingestion(sample_pdf, client_ctx):
    with open(sample_pdf, "rb") as fh:
        r = client_ctx.post(
            "/api/v1/syllabus/upload",
            files={"file": ("sample.pdf", fh, "application/pdf")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["file_name"] == "sample.pdf"
    assert len(body["modules"]) >= 1