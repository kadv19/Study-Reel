"""FastAPI application: StudyReel backend (Phase 1 standalone pipeline)."""

import io
import uuid
import zipfile
from pathlib import Path

from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.db.database import (
    get_carousel,
    get_module,
    get_pipeline_state,
    init_db,
    save_carousel,
    save_syllabus,
    set_pipeline_state,
)
from app.engine.gemini_client import generate_topics_for_module
from app.ingestion.pipeline import process_pdf
from app.renderer.render import render_carousel
from app.schemas import Carousel, MicroTopic, Slide, Syllabus

app = FastAPI(title="StudyReel Backend", version="0.2.0")

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
RENDER_DIR = Path(__file__).resolve().parents[2] / "renders"
UPLOAD_DIR.mkdir(exist_ok=True)
RENDER_DIR.mkdir(exist_ok=True)


class CarouselRenderRequest(BaseModel):
    """Approved topics (post-HITL) ready to render into a carousel."""

    module_name: str = Field(..., max_length=60)
    subject_code: Optional[str] = Field(None, max_length=20)
    topics: list[MicroTopic] = Field(..., min_length=1, max_length=10)


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


@app.post("/api/v1/carousels/render")
def render_approved_carousel(req: CarouselRenderRequest) -> dict:
    """Render approved MicroTopics into 1080x1350 PNG slides (Playwright)."""
    slides = []
    for i, topic in enumerate(req.topics):
        slide_type = "mixed" if topic.code_block else "text"
        slides.append(Slide(slide_type=slide_type, index=i, topic=topic))

    carousel = Carousel(
        carousel_id=uuid.uuid4().hex[:8],
        module_name=req.module_name,
        subject_code=req.subject_code,
        slides=slides,
    )

    set_pipeline_state("PROCESSING", "rendering", 0.3, f"Rendering {len(slides)} slides")

    out_dir = RENDER_DIR / carousel.carousel_id
    try:
        pngs = render_carousel(carousel, out_dir=out_dir)
    except Exception as exc:
        set_pipeline_state("FAILED", "rendering", 0.0, f"Rendering failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Rendering failed: {exc}") from exc

    module_id = _latest_module_id()
    carousel_db_id = save_carousel(carousel, module_id, output_dir=str(out_dir))
    set_pipeline_state(
        "DONE", "rendering", 1.0,
        f"Rendered {len(pngs)} slides (carousel id={carousel_db_id})",
    )
    return {
        "id": carousel_db_id,
        "carousel_id": carousel.carousel_id,
        "module_name": carousel.module_name,
        "slide_count": len(pngs),
        "output_dir": str(out_dir),
        "slides": [p.name for p in pngs],
    }


@app.get("/api/v1/carousels/{carousel_id}/export")
def export_carousel(carousel_id: int) -> StreamingResponse:
    """Download all rendered PNG slides as a ZIP archive."""
    record = get_carousel(carousel_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Carousel {carousel_id} not found")

    out_dir = Path(record["output_dir"])
    if not out_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Rendered slides missing for carousel {carousel_id}")

    pngs = sorted(out_dir.glob("slide_*.png"))
    if not pngs:
        raise HTTPException(status_code=404, detail="No rendered slides found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for png in pngs:
            zf.write(png, arcname=png.name)
    buf.seek(0)

    filename = f"studyreel_carousel_{record['id']}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _latest_module_id() -> int:
    """Resolve a module_id for carousel FK (latest syllabus's first module)."""
    from app.db.database import _connect

    with _connect() as conn:
        row = conn.execute("SELECT id FROM modules ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"] if row else 1