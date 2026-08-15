# StudyReel — Backend

Syllabus PDF → micro-learning carousels. Phase 1: standalone pipeline.

## Quick start

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# optional: setup file
cp .env.example .env   # add GEMINI_API_KEY
```

Run the server:

```bash
uvicorn app.main:app --reload
```

Docs at http://127.0.0.1:8000/docs (Swagger). API tests:

```bash
pytest tests/ -v
```

## Structure

```
backend/
├── app/
│   ├── main.py            # FastAPI app: /api/v1/health, /status, /syllabus/upload
│   ├── schemas.py         # THE CONTRACT: MicroTopic, Slide, Carousel, Syllabus
│   ├── ingestion/         # pdfplumber → module boundary → noise clean → topics
│   ├── engine/            # Gemini 2.5 client + cached, Pydantic-validated output
│   ├── db/                # SQLite: syllabi, modules, carousels, pipeline_state
│   └── renderer/          # (Sprint 3) Jinja2 + Tailwind + Playwright → PNG
├── tests/                 # 25 tests: schemas, boundary, pipeline, API, regressions
└── requirements.txt
```

## Documentation

Full project documentation is available in the `docs/` folder:
- [docs/SETUP.md](../docs/SETUP.md) — Step-by-step setup guide for fresh machines.
- [docs/API.md](../docs/API.md) — API endpoints, request/response models, and curl commands.
- [docs/SPRINT_LOG.md](../docs/SPRINT_LOG.md) — Sprint tracking, shipped features, and meeting minutes.

## Data flow

```
POST /api/v1/syllabus/upload (PDF)
  → ingestion.process_pdf (pdfplumber + boundary regex + noise cleaning)
  → SQLite (syllabus + modules rows)
  → typed Syllabus response
  [Sprint 2+] → engine.generate_topics (Gemini, validated by MicroTopic)
  [Sprint 3]  → renderer → PNG carousel → ZIP
```

## Status flags (circuit-breaker ready)

`pipeline_state` table: `IDLE` → `PROCESSING` → `DONE | FAILED | NEEDS_SUPERVISION`.
`NEEDS_SUPERVISION` is the Phase 2 hook for the HITL dashboard.

## Ownership map

| Layer | Owner | Status |
|---|---|---|
| Schemas (MicroTopic) | P1 + P3 | ✅ done |
| Ingestion layer | P1 | ✅ done (25/25 tests) |
| SQLite | P1 | ✅ done |
| FastAPI endpoints | P1 | ✅ done |
| Gemini client | P2 | ✅ live-verified (genai SDK, gemini-3.5-flash, repair loop) |
| Renderer | P3 | ✅ done (Jinja2 + Tailwind + Playwright, 31/31 tests) |
| Dashboard & Docs | P4 | ✅ done (Streamlit UI & docs suite) |