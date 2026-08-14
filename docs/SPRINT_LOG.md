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
