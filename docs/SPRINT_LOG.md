# StudyReel — Sprint Log & Meeting Minutes

This log tracks sprint progress, deliverables, decisions, and blockers across all project phases.

---

## 📅 Sprint 1: Project Scaffolding & Ingestion Pipeline
**Dates:** 2026-08-01 – 2026-08-13  
**Lead:** P1 (Architecture & Ingestion)

### Shipped:
- Core contracts defined in `app/schemas.py` (`MicroTopic`, `Slide`, `Carousel`, `ExtractedModule`, `Syllabus`, `PipelineStatus`).
- PDF ingestion pipeline with `pdfplumber`, boundary detection regex (Roman numerals, single-module fallback), noise cleaning (ISBN, CO/PO, credits removal).
- SQLite persistence layer in `app/db/database.py` with singleton pipeline state.
- FastAPI endpoints: `GET /api/v1/health`, `GET /api/v1/status`, `POST /api/v1/syllabus/upload`.
- Comprehensive test suite (25/25 tests passing covering schemas, boundary, API, and example syllabi regressions).

### Blockers / Gotchas:
- En-dash separators in VTU syllabi (`Module – 1`) resolved via regex normalization.
- Trailing lecture hour strings stripped from topics.

---

## 📅 Sprint 2: AI/ML Engine & Gemini Integration
**Dates:** 2026-08-14 – 2026-08-21  
**Lead:** P2 (AI/ML Engine)

### Shipped:
- Gemini 2.5 Flash client (`gemini-3.6-flash` + failover) live-validated via `tests/test_gemini_live.py` (5 modules, 5/5 green 2026-09-11).
- `PostMetadata` generation (`post_metadata.py`) with caption/hashtags/cover_slide — `tests/test_post_metadata.py` 3/3 green.
- Prompt tuning exam-focused, cache schema v2, Ollama fallback `qwen2.5:7b`.

---

## 📅 Sprint 3: Rendering Engine & Visual Layouts
**Dates:** 2026-08-22 – 2026-08-29  
**Lead:** P3 (Rendering & Visual Design)

### Shipped:
- Jinja2 templates 1080×1350 dark theme (`text.html`, `code.html`, `mixed.html`) + local woff2 fonts.
- Playwright headless `render_carousel()` pipeline — `tests/test_renderer.py` 6/6 green (2026-09-11).
- InstaClone stub `instaclone/app.py` (port 8100) with `POST /api/posts`, `GET /api/feed`, `GET /feed` — `tests/test_instaclone.py` 7/7 green.

---

## 📅 Sprint 4: Admin Dashboard & Documentation
**Dates:** 2026-08-14 (Scaffold) – 2026-09-05 (Final Polish)  
**Lead:** P4 (Dashboard & Documentation)

### Shipped:
- `dashboard/studyreel_dashboard.py` Streamlit admin dashboard with dark brand theme.
- Interactive syllabus PDF upload and 2-second status polling with progress bar.
- Extracted module viewer with expanders and topic lists.
- Human-in-the-loop (HITL) manual review interface with real-time character limit validation.
- Carousel preview canvas and JSON export functionality.
- Repository documentation suite: `docs/SETUP.md`, `docs/API.md`, `docs/SPRINT_LOG.md`.

---

## 📝 Team Meeting Minutes

### Meeting #1 (2026-08-14)
**Attendees:** P1 (Lead), P2 (Engine), P3 (Renderer), P4 (Dashboard/Docs)

#### Agenda & Decisions:
1. **Schema Stability:** Confirmed `backend/app/schemas.py` is the single source of truth; any edits require P1 approval.
2. **Dashboard Delivery:** P4 delivered the Phase 1 Streamlit admin UI and complete documentation structure.
3. **Integration Handshake:** P2 and P1 agreed on the generation endpoint contract for the HITL manual review editor.
4. **Test Suite Mandate:** Every team member must run `pytest tests/` before and after their changes to keep all 25 tests green.

---

## 📅 Sprint 4 — Phase 2 Extension: Publish Queue UI
**Dates:** 2026-08-29 – 2026-09-05
**Lead:** P4 (Dashboard & Docs)

### Shipped (Phase 2):
- `dashboard/studyreel_dashboard.py` extended with a new **🚀 Publish** tab:
  - Caption text area pre-filled with module-name template + CTA.
  - Hashtag input with minimum-3 validation.
  - "Publish Now" and "📅 Schedule for later" controls calling `POST /api/v2/publish`.
  - Status chip: `queued` (blue) → `published` (green) with InstaClone feed link.
  - Published posts table (`GET /api/v2/posts`) with 5-second auto-polling while any post is queued.
- Sidebar **🔗 Connect Account** section:
  - "Connect (Simulated)" button → `POST /api/v2/oauth/connect` → token + 60-day expiry countdown chip.
  - "Revoke" button → `POST /api/v2/oauth/revoke`.
- `dashboard/api_client.py` extended with 5 v2 helpers:
  `publish_carousel`, `fetch_published_posts`, `fetch_v2_status`, `connect_oauth`, `revoke_oauth`.
- `docs/API.md` updated — Section 7 replaced with full v2 endpoint docs including request/response examples.
- `docs/SPRINT_LOG.md` updated with Phase 2 sprint entry and Meeting #2 minutes.
- `prompts/p4_phase2_publish_ui.md` added for reproducible prompt history.

### Phase 2 Key Decision:
**Standalone InstaClone first (Phase 2), real Meta API later (Phase 3).**
The Publisher abstraction in `backend/app/publisher/` means this is a config-only swap:
`PUBLISHER=instaclone` → `PUBLISHER=instagram` in `backend/.env`. No dashboard or API changes required.

### Guardrails observed:
- `schemas.py` not touched — `PostMetadata` and `PublishRequest` consumed read-only.
- `backend/app/publisher/` not touched — only HTTP endpoints consumed.
- Dashboard kept under 350 lines (317 lines).
- Tests 2026-09-11: backend 53/53 green + instaclone 7/7 green (60 total). No Playwright failure.

---

## 📅 Sprint 5: Phase 2 Publisher Abstraction — DONE
**Dates:** 2026-08-29 – 2026-09-11  
**Lead:** P1 (Publisher & Pipeline) — Phase 2 closure 2026-09-11

### Shipped:
- `backend/app/schemas.py:132` `PostMetadata` (caption 2200, hashtags 3-30 `_lower_strip`) + `PublishRequest` (carousel_id, caption, hashtags, schedule_at).
- `backend/app/publisher/` abstraction: `publisher.py:17` `PublishResult`/`Publisher` protocol, `instaclone.py:17` PNG copy to `instaclone/data/slides/{post_id}/` + POST to `INSTACLONE_URL:8100`, `instagram.py:24` Graph stub (60d token), `store.py:12` `studyreel_publisher.db` (published/scheduled/oauth), `__init__.py:10` `PUBLISHER` env switch.
- `backend/app/api_v2.py:31` `POST /publish` (queue vs immediate), `GET /posts`, `GET /status`, `POST /oauth/*`, scheduler `5s` polling `due_scheduled_posts`.
- `backend/app/main.py:29` `v0.3.0` + `include_router` + `start_scheduler()` on startup.
- `backend/.env.example:17` `PUBLISHER=instaclone`/`INSTACLONE_URL`/`PUBLISHER_DB` + `requests` in `requirements.txt:12`.
- `tests/test_publisher.py:28` (protocol/store/oauth) + `tests/test_api_v2.py:45` (mocked `get_publisher`) — 7/7 green; full suite 60/60.
- Live smoke 2026-09-11: immediate `a748ffa4` + scheduled `d212ae23` + oauth 60d verified on `127.0.0.1:8100`/`8000`.

### Phase 2 Closure Decision:
Publisher seam proven — `PUBLISHER=instaclone` today, `instagram` tomorrow via env only. No dashboard/API contract break. Next: UI polish, downloadable packaging, smooth run.

---

## 📝 Team Meeting Minutes

### Meeting #2 (2026-08-29)
**Attendees:** P1 (Lead), P4 (Dashboard/Docs)

#### Agenda & Decisions:
1. **Phase 2 Kickoff:** Agreed to target InstaClone (port 8100) as the publish destination for Phase 2.
   Phase 3 will swap to the real Meta Graph API via a `PUBLISHER` env-var change only.
2. **P4 Scope confirmed:** Publish Queue tab, OAuth UX, v2 API docs. P1 owns the v2 endpoints; P4 consumes them.
3. **HTTP contract locked:** `POST /api/v2/publish` returns `{media_id, feed_url, status, provider}`.
   `GET /api/v2/posts` returns list with `{id, provider, media_id, carousel_id, caption, hashtags, feed_url, published_at}`.
   P4 must not add fields or rename — consume exactly what P1 provides.
4. **Port discipline re-confirmed:** backend 8000, InstaClone 8100, dashboard 8501. No guessing.

### Meeting #3 (2026-09-11) — Phase 2 DONE
**Attendees:** P1, P2, P3, P4

#### Agenda & Decisions:
1. **Verification:** `pytest` 53 backend +7 instaclone =60/60 green (76s). Live smoke immediate `a748ffa4` + scheduled `5s poll` + oauth 60d on `8100`/`8000`.
2. **Closure:** Publisher abstraction closed, `v0.3.0` tagged. `schemas.py` contract frozen, `PUBLISHER` switch validated.
3. **Next:** UI polish (Streamlit + InstaClone feed dark theme), downloadable packaging (`pip install`, `docker`, `studyreel.db` + `studyreel_publisher.db`), smooth run (ports 8000/8100/8501, one-command `uvicorn` + `streamlit run`).

