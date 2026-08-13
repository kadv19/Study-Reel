"""FastAPI application: StudyReel backend (Phase 1 standalone pipeline)."""

import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.db.database import get_pipeline_state, init_db, save_syllabus, set_pipeline_state
from app.ingestion.pipeline import process_pdf
from app.schemas import Syllabus

app = FastAPI(title="StudyReel Backend", version="0.1.0")

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "studyreel"}


@app.get("/api/v1/status")
def status() -> dict:
    return get_pipeline_state()


@app.post("/api/v1/syllabus/upload", response_model=Syllabus)
async def upload_syllabus(file: UploadFile = File(...)) -> Syllabus:
    """Upload a syllabus PDF, run ingestion, persist, return typed modules."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    set_pipeline_state("PROCESSING", "ingestion", 0.1, f"Uploading {file.filename}")

    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    dest.write_bytes(await file.read())

    try:
        syllabus = process_pdf(dest)
        syllabus.file_name = file.filename  # return the original name, not the stored one
    except Exception as exc:
        set_pipeline_state("FAILED", "ingestion", 0.0, str(exc))
        raise HTTPException(status_code=422, detail=f"Ingestion failed: {exc}") from exc

    syllabus_id = save_syllabus(syllabus)
    set_pipeline_state("DONE", "ingestion", 1.0, f"Extracted {len(syllabus.modules)} modules (id={syllabus_id})")

    return syllabus


@app.get("/api/v1/modules/{module_number}/topics")
def get_topics(module_number: int) -> dict:
    """Placeholder for the generation stage; wired to Gemini in Sprint 2."""
    return {"module": module_number, "note": "Generation endpoint lands with the AI engine"}