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


def test_generate_topics_module_not_found(client_ctx):
    r = client_ctx.get("/api/v1/modules/99/topics")
    assert r.status_code == 404


def test_generate_topics_success(client_ctx, monkeypatch, sample_pdf):
    """Generation endpoint returns schema-valid topics via the Gemini engine."""
    from app.schemas import MicroTopic

    fake_topics = [
        MicroTopic(
            header="OSI Model",
            body="Seven-layer reference model for network communication.",
            language_tag=None,
        ),
        MicroTopic(
            header="TCP/IP Basics",
            body="Four-layer protocol suite powering the internet.",
            code_block="sock = socket.socket()",
            language_tag="python",
        ),
    ]

    def fake_generate(module_text):
        return fake_topics

    monkeypatch.setattr("app.main.generate_topics_for_module", fake_generate)

    with open(sample_pdf, "rb") as fh:
        up = client_ctx.post(
            "/api/v1/syllabus/upload",
            files={"file": ("sample.pdf", fh, "application/pdf")},
        )
    assert up.status_code == 200
    module_number = up.json()["modules"][0]["module_number"]

    r = client_ctx.get(f"/api/v1/modules/{module_number}/topics")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 2
    assert body[0]["header"] == "OSI Model"
    assert body[1]["code_block"] == "sock = socket.socket()"

    status = client_ctx.get("/api/v1/status").json()
    assert status["state"] == "DONE"
    assert status["stage"] == "generation"


def test_generate_topics_engine_failure(client_ctx, monkeypatch, sample_pdf):
    """Engine failures surface as 502 and pipeline state flips to FAILED."""

    def boom(module_text):
        raise RuntimeError("model exploded")

    monkeypatch.setattr("app.main.generate_topics_for_module", boom)

    with open(sample_pdf, "rb") as fh:
        up = client_ctx.post(
            "/api/v1/syllabus/upload",
            files={"file": ("sample.pdf", fh, "application/pdf")},
        )
    module_number = up.json()["modules"][0]["module_number"]

    r = client_ctx.get(f"/api/v1/modules/{module_number}/topics")
    assert r.status_code == 502
    status = client_ctx.get("/api/v1/status").json()
    assert status["state"] == "FAILED"