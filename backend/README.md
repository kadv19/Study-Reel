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
├── tests/                 # 20 tests: schemas, boundary, pipeline, API
└── requirements.txt
```

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
|-------|-------|--------|
| Schemas (MicroTopic) | P1 (you) + P3 | ✅ done |
| Ingestion layer | P1 | ✅ done (20/20 tests) |
| SQLite | P1 | ✅ done |
| FastAPI endpoints | P1 | ✅ done |
| Gemini client | P2 | 🔲 interface ready, needs API key test |
| Renderer | P3 | 🔲 Sprint 3 |
| Dashboard | P4 | 🔲 Sprint 4 |