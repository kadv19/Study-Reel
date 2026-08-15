"""FastAPI application: StudyReel backend (Phase 1 standalone pipeline)."""

import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.db.database import (
    get_module,
    get_pipeline_state,
    init_db,
    save_syllabus,
    set_pipeline_state,
)
from app.engine.gemini_client import generate_topics_for_module
from app.ingestion.pipeline import process_pdf
from app.schemas import MicroTopic, Syllabus

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


@app.get("/api/v1/modules/{module_number}/topics", response_model=list[MicroTopic])
def generate_module_topics(module_number: int) -> list[MicroTopic]:
    """Generate AI micro-topics for a stored module via the Gemini engine.

    Requires a syllabus upload first (the module must exist in SQLite).
    Pipeline state is driven through PROCESSING -> DONE / FAILED.
    """
    record = get_module(module_number)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Module {module_number} not found — upload a syllabus first")

    module = record["module"]
    module_text = "\n".join(module["topic_strings"])
    title = module.get("module_title") or f"Module {module_number}"

    set_pipeline_state("PROCESSING", "generation", 0.2, f"Generating topics for {title}")

    try:
        topics = generate_topics_for_module(module_text)
    except Exception as exc:
        set_pipeline_state("FAILED", "generation", 0.0, f"Generation failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Generation failed: {exc}") from exc

    set_pipeline_state(
        "DONE", "generation", 1.0,
        f"Generated {len(topics)} topics for {title}",
    )
    return topics