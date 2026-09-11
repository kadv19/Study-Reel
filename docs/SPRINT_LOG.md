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

### In Progress:
- Gemini 2.5 Flash client validation against `MicroTopic` pydantic schema.
- System prompt tuning to maintain header <= 30 chars, body <= 140 chars, and code block formatting.
- Caching layer enhancement using module text MD5 checksums.

---

## 📅 Sprint 3: Rendering Engine & Visual Layouts
**Dates:** 2026-08-22 – 2026-08-29  
**Lead:** P3 (Rendering & Visual Design)

### In Progress:
- Jinja2 template definitions for 1080x1350 Instagram slides (`text.html`, `code.html`, `mixed.html`).
- Playwright headless rendering pipeline for high-DPI screenshot generation.
- Stress testing for text overflows and Pygments syntax highlighting.

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
- Tests run before and after: baseline 32 pass / 1 pre-existing Playwright failure maintained.

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

