# OpenClaw / AI Assistant Handoff Notes — StudyReel Backend (P1 Scope)

State snapshot for whoever picks this up next. Last updated: 2026-08-13 by OpenCode.

## What's DONE (delete nothing without reading this first)

- `app/schemas.py` — the shared contract. MicroTopic (header ≤30, body ≤140, code ≤22 lines ≤62 chars, language whitelist), Slide, Carousel (ordered indices enforced), Syllabus, ExtractedModule, PipelineStatus.
- `app/ingestion/` — parser (pdfplumber), boundary (Module regex + Roman numeral support + single-module fallback), noise cleaner (ISBN/CO/PO/credits/page numbers), pipeline orchestrator.
- `app/db/database.py` — SQLite: syllabi, modules, carousels, pipeline_state. `init_db()` runs on startup.
- `app/main.py` — FastAPI: health, status, syllabus/upload. Uploads stored under `backend/uploads/` with uuid prefix.
- Tests: 25 passing (`pytest tests/ -v`). venv at `backend/.venv`.
- Smoke test passed: server boots, real PDF upload → 1 module extracted → state DONE. Use the StudyReel PDF in sibling docs as a test file (no Module headings → exercises fallback).
- **Real-syllabus hardening done 2026-08-13:** ingestion now handles `Module – 1` (en-dash), `Modules -1` (plural), drops reference/book sections, cuts at "Practical Components"/"Scheme of Examination", strips trailing lecture-hour counts. Verified against both PDFs in `examples/`. Regression suite: `tests/test_examples.py` (5 tests, skip if examples absent).

## What's NEXT (Sprint 2 — generation stage)

1. **Gemini test (P2's job, but verifiable):** `app/engine/gemini_client.py` is ready. Interface `generate_topics_for_module(module_text)` returns `list[MicroTopic]`. Needs `GEMINI_API_KEY` in env. Cache dir optional via constructor. **Do NOT hit the API without a key set — it raises RuntimeError.**
2. **Wire `/api/v1/syllabus/upload` → generation:** after `save_syllabus`, call engine per module, build Carousel objects, `save_carousel()`. Keep stage updates in pipeline_state (PROCESSING/DONE/FAILED).
3. **Manual review endpoint (later):** `/api/v1/modules/{n}/topics` is a stub — needs to return topics after generation for the admin dashboard to review before rendering.

## What's NEXT after that (Sprint 3 — rendering, P3's job)

- `app/renderer/__init__.py` exists; nothing inside. Playwright package installed in venv but **browser binaries NOT installed** — needs `playwright install chromium` (system Chromium is NOT used by Playwright).
- Templates: jinja2 installed. Local .woff2 fonts go under `app/renderer/static/`.

## Notes / gotchas

- The noise cleaner strips trailing stray commas but **keeps sentence periods** — deliberate.
- `pipeline_state` uses `id=1` singleton row.
- `test_status_defaults_to_idle` asserts state is in valid set (not exactly IDLE) because tests share one DB and ordering varies.
- Deprecation warnings (on_event, httpx testclient) are harmless — don't chase them.

## Team coordination

- **Do not** edit `schemas.py` without checking with P3 (they build the renderer against it).
- P2 owns Gemini prompt tuning (temperature 0.4, JSON mime). Interface stability > prompt cleverness.
- Push to GitHub repo when created; branch `dev`, PRs require P1 approval.