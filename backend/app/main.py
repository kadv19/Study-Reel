"""FastAPI application: StudyReel backend (Phase 1 standalone pipeline)."""

import io
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from typing import Literal, Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.auth import current_user
from app.db.database import (
    count_active_jobs,
    count_syllabi_since,
    create_job,
    get_carousel,
    get_carousel_owner,
    get_job_for_user,
    get_job_queue_position,
    get_latest_job,
    get_module,
    init_db,
    save_carousel,
    save_syllabus,
    update_job,
)
from app.engine.gemini_client import generate_topics_for_module
from app.ingestion.parser import extract_text
from app.ingestion.pipeline import process_pdf
from app.jobs import (
    job_gate,
    limits_lock,
    max_active_jobs_per_user,
    max_syllabi_per_day,
)
from app.renderer.render import render_carousel
from app.schemas import Carousel, MicroTopic, Slide, Syllabus
from app.api_v2 import router as api_v2_router, start_scheduler
from app.api_catalog import router as catalog_router
from app.api_users import router as users_router

app = FastAPI(title="StudyReel Backend", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://study-reel-instaclone.onrender.com",
        "https://studyreel-instaclone.onrender.com",
        "http://localhost:8100",
        "http://127.0.0.1:8100",
        "capacitor://localhost",
        "http://localhost",
        "http://127.0.0.1:8501",
        "http://localhost:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_v2_router)
app.include_router(catalog_router)
app.include_router(users_router)

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
RENDER_DIR = Path(__file__).resolve().parents[2] / "renders"
UPLOAD_DIR.mkdir(exist_ok=True)
RENDER_DIR.mkdir(exist_ok=True)


def _idle_job(owner_user_id: str) -> dict:
    return {
        "id": None,
        "job_id": None,
        "owner_user_id": owner_user_id,
        "stage": None,
        "state": "IDLE",
        "progress": 0.0,
        "message": "No jobs yet",
        "created_at": None,
        "updated_at": None,
        "queue_position": 0,
        "position": 0,
    }


def _enforce_job_limits(owner_user_id: str, check_daily_syllabi: bool = False) -> None:
    if count_active_jobs(owner_user_id) >= max_active_jobs_per_user():
        raise HTTPException(
            status_code=429,
            detail="You already have an active job. Please wait for it to finish.",
        )
    if check_daily_syllabi:
        limit = max_syllabi_per_day()
        since = datetime.now(timezone.utc) - timedelta(days=1)
        if count_syllabi_since(owner_user_id, since) >= limit:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Daily limit reached: you can upload {limit} syllabi per day. "
                    "Please try again tomorrow."
                ),
            )


@contextmanager
def _job_slot(job_id: int, stage: str, message: str):
    if not job_gate.try_acquire():
        position = get_job_queue_position(job_id)
        update_job(
            job_id,
            "QUEUED",
            stage,
            0.0,
            f"Queued — position {position}",
        )
        job_gate.acquire()
    try:
        update_job(job_id, "PROCESSING", stage, 0.2, message)
        yield
    finally:
        job_gate.release()


def _create_job(
    owner_user_id: str,
    stage: str,
    state: str,
    progress: float,
    message: str,
    check_daily_syllabi: bool = False,
) -> dict:
    with limits_lock:
        _enforce_job_limits(owner_user_id, check_daily_syllabi=check_daily_syllabi)
        return create_job(owner_user_id, stage, state, progress, message)


class CarouselRenderRequest(BaseModel):
    """Approved topics (post-HITL) ready to render into a carousel."""

    module_name: str = Field(..., max_length=60)
    subject_code: Optional[str] = Field(None, max_length=20)
    topics: list[MicroTopic] = Field(..., min_length=1, max_length=20)


class TopicsGenerateRequest(BaseModel):
    """Tailoring options for topic generation — dropdown-driven upload flow."""

    depth_format: Literal["detailed", "short", "diagram", "both", "auto"] = "detailed"
    tone: Literal["eli5", "professional", "default"] = "default"
    slide_count: int = Field(10, ge=3, le=20)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    start_scheduler()


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "studyreel"}


@app.get("/api/v1/status")
def status(job_id: int | None = None, user: dict = Depends(current_user)) -> dict:
    if job_id is not None:
        job = get_job_for_user(job_id, user["id"])
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
    else:
        job = get_latest_job(user["id"])
    if not job:
        return _idle_job(user["id"])
    position = get_job_queue_position(job["id"]) if job["state"] == "QUEUED" else 0
    return {
        **job,
        "job_id": job["id"],
        "queue_position": position,
        "position": position,
    }


@app.post("/api/v1/syllabus/upload", response_model=Syllabus)
async def upload_syllabus(
    file: UploadFile = File(...),
    resource_file: UploadFile | None = File(default=None),
    user: dict = Depends(current_user),
) -> Syllabus:
    """Upload a syllabus PDF, optionally a resource PDF, run ingestion, persist, return typed modules."""
    owner = user["id"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    if resource_file and resource_file.filename and not resource_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Resource file must be a PDF")

    job = _create_job(
        owner,
        "ingestion",
        "PROCESSING",
        0.1,
        f"Uploading {file.filename}",
        check_daily_syllabi=True,
    )

    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    dest.write_bytes(await file.read())

    resource_text: str | None = None
    if resource_file and resource_file.filename:
        rdest = UPLOAD_DIR / f"{uuid.uuid4().hex}_{resource_file.filename}"
        rdest.write_bytes(await resource_file.read())
        try:
            resource_text = await run_in_threadpool(extract_text, rdest)
            # cap to avoid huge prompt
            if len(resource_text) > 8000:
                resource_text = resource_text[:8000]
        except Exception as exc:
            # non-fatal: keep resource_text None but log
            resource_text = None
            update_job(
                job["id"],
                "PROCESSING",
                "ingestion",
                0.15,
                f"Resource parse warning: {exc}",
            )

    try:
        syllabus = await run_in_threadpool(process_pdf, dest)
        syllabus.file_name = file.filename  # return the original name, not the stored one
    except Exception as exc:
        update_job(job["id"], "FAILED", "ingestion", 0.0, str(exc))
        raise HTTPException(status_code=422, detail=f"Ingestion failed: {exc}") from exc

    try:
        syllabus_id = await run_in_threadpool(
            save_syllabus, syllabus, owner_user_id=owner, resource_text=resource_text
        )
    except Exception as exc:
        update_job(job["id"], "FAILED", "ingestion", 0.0, f"Save failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Save failed: {exc}") from exc

    update_job(
        job["id"],
        "DONE",
        "ingestion",
        1.0,
        f"Extracted {len(syllabus.modules)} modules (id={syllabus_id})",
    )

    return syllabus


@app.get("/api/v1/modules/{module_number}/topics", response_model=list[MicroTopic])
def generate_module_topics(
    module_number: int,
    user: dict = Depends(current_user),
) -> list[MicroTopic]:
    """Generate AI micro-topics for a stored module via the Gemini engine.

    Requires a syllabus upload first (the module must exist in the database
    and be owned by the caller).
    Pipeline state is driven through PROCESSING -> DONE / FAILED.
    """
    record = get_module(module_number, owner_user_id=user["id"])
    if record is None:
        raise HTTPException(status_code=404, detail=f"Module {module_number} not found — upload a syllabus first")

    module = record["module"]
    module_text = "\n".join(module["topic_strings"])
    title = module.get("module_title") or f"Module {module_number}"

    job = _create_job(user["id"], "generation", "QUEUED", 0.0, f"Queued for {title}")

    try:
        with _job_slot(job["id"], "generation", f"Generating topics for {title}"):
            topics = generate_topics_for_module(module_text)
    except HTTPException as exc:
        update_job(job["id"], "FAILED", "generation", 0.0, f"Generation failed: {exc.detail}")
        raise
    except Exception as exc:
        update_job(job["id"], "FAILED", "generation", 0.0, f"Generation failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Generation failed: {exc}") from exc

    update_job(
        job["id"],
        "DONE",
        "generation",
        1.0,
        f"Generated {len(topics)} topics for {title}",
    )
    return topics


@app.post("/api/v1/modules/{module_number}/topics", response_model=list[MicroTopic])
def generate_module_topics_post(
    module_number: int,
    req: TopicsGenerateRequest,
    user: dict = Depends(current_user),
) -> list[MicroTopic]:
    """POST variant with tailoring options — dropdown-driven flow.

    Takes depth_format, tone, slide_count and optional resource_text linked to the syllabus.
    Keeps GET for backward compatibility.
    """
    record = get_module(module_number, owner_user_id=user["id"])
    if record is None:
        raise HTTPException(status_code=404, detail=f"Module {module_number} not found — upload a syllabus first")

    module = record["module"]
    module_text = "\n".join(module["topic_strings"])
    title = module.get("module_title") or f"Module {module_number}"
    # resource_text is stored per syllabus; get_module now returns it
    resource_text = record.get("resource_text")

    job = _create_job(user["id"], "generation", "QUEUED", 0.0, f"Queued for {title}")

    try:
        with _job_slot(
            job["id"],
            "generation",
            f"Generating topics for {title} [{req.depth_format}/{req.tone} ×{req.slide_count}]",
        ):
            topics = generate_topics_for_module(
                module_text,
                depth_format=req.depth_format,
                tone=req.tone,
                slide_count=req.slide_count,
                resource_text=resource_text,
            )
    except HTTPException as exc:
        update_job(job["id"], "FAILED", "generation", 0.0, f"Generation failed: {exc.detail}")
        raise
    except Exception as exc:
        update_job(job["id"], "FAILED", "generation", 0.0, f"Generation failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Generation failed: {exc}") from exc

    update_job(
        job["id"],
        "DONE",
        "generation",
        1.0,
        f"Generated {len(topics)} topics for {title}",
    )
    return topics


@app.post("/api/v1/carousels/render")
def render_approved_carousel(
    req: CarouselRenderRequest,
    user: dict = Depends(current_user),
) -> dict:
    """Render approved MicroTopics into 1080x1350 PNG slides (Playwright)."""
    slides = []
    for i, topic in enumerate(req.topics):
        has_diagram = bool(getattr(topic, "diagram", None))
        if has_diagram:
            slide_type = "diagram"
        elif topic.code_block:
            slide_type = "mixed"
        else:
            slide_type = "text"
        slides.append(Slide(slide_type=slide_type, index=i, topic=topic))

    carousel = Carousel(
        carousel_id=uuid.uuid4().hex[:8],
        module_name=req.module_name,
        subject_code=req.subject_code,
        slides=slides,
    )

    owner = user["id"]
    module_id = _latest_module_id(owner_user_id=owner)
    if module_id is None:
        raise HTTPException(status_code=400, detail="Upload a syllabus before rendering a carousel")

    job = _create_job(
        owner, "rendering", "QUEUED", 0.0, f"Queued to render {len(slides)} slides"
    )

    out_dir = RENDER_DIR / carousel.carousel_id
    try:
        with _job_slot(job["id"], "rendering", f"Rendering {len(slides)} slides"):
            update_job(job["id"], "PROCESSING", "rendering", 0.3, f"Rendering {len(slides)} slides")
            pngs = render_carousel(carousel, out_dir=out_dir)
            carousel_db_id = save_carousel(carousel, module_id, output_dir=str(out_dir))
    except Exception as exc:
        update_job(job["id"], "FAILED", "rendering", 0.0, f"Rendering failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Rendering failed: {exc}") from exc

    update_job(
        job["id"],
        "DONE",
        "rendering",
        1.0,
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
def export_carousel(
    carousel_id: int,
    user: dict = Depends(current_user),
) -> StreamingResponse:
    """Download all rendered PNG slides as a ZIP archive."""
    record = get_carousel(carousel_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Carousel {carousel_id} not found")
    if get_carousel_owner(carousel_id) != user["id"]:
        raise HTTPException(status_code=403, detail="Not owner of this carousel")

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


@app.get("/api/v1/carousels/{carousel_id}/slides/{slide_index}.png")
def get_carousel_slide_png(
    carousel_id: int,
    slide_index: int,
    user: dict = Depends(current_user),
) -> FileResponse:
    """Serve one rendered slide as a PNG so the cabinet can show real previews."""
    record = get_carousel(carousel_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Carousel {carousel_id} not found")
    if get_carousel_owner(carousel_id) != user["id"]:
        raise HTTPException(status_code=403, detail="Not owner of this carousel")
    if not record.get("output_dir"):
        raise HTTPException(status_code=404, detail=f"Rendered slides missing for carousel {carousel_id}")
    out_dir = Path(record["output_dir"])
    png = out_dir / f"slide_{slide_index + 1:02d}.png"
    if not png.is_file():
        raise HTTPException(status_code=404, detail=f"Slide {slide_index} not found for carousel {carousel_id}")
    return FileResponse(
        png,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=86400"},
    )


def _latest_module_id(owner_user_id: str) -> int | None:
    """Resolve the latest module_id owned by this user for the carousel FK."""
    from app.db.database import _connect, _exec

    conn = _connect()
    try:
        cur = _exec(
            conn,
            "SELECT m.id FROM modules m JOIN syllabi s ON s.id=m.syllabus_id WHERE s.owner_user_id=%s ORDER BY m.id DESC LIMIT 1",
            (owner_user_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    return row["id"] if row else None
