# StudyReel — Exact Prompts for P2, P3, P4 (AI-Assisted Setup)

Give each teammate their copy-paste prompt. They must run these in order (Setup → Task prompts). Phase 1 (ingestion → Gemini → render → dashboard) is **COMPLETE and on main**. Phase 2 = the **standalone InstaClone** delivery app (mini-Instagram) + publish pipeline, so the project proves end-to-end delivery without Meta's Graph API app-review bottleneck. Real FB/IG becomes Phase 3 via a swap-in adapter.

**They must NOT recreate anything that exists** — only build on it.

---

## Common Setup (ALL MEMBERS — run once)

```
You are working on StudyReel, a 6-week major project. The repo is at:
{repo_path}/studyreel

First, read these files THOROUGHLY before writing any code:
1. backend/README.md — project overview and ownership map
2. backend/app/schemas.py — THE CONTRACT. Every layer builds against these types.
3. HANDOFF_OPENCLAW.md — current project state and gotchas
4. docs/SPRINT_LOG.md — what shipped so far and meeting decisions

Phase 1 is DONE: syllabus ingestion, Gemini engine (with quota failover +
Ollama fallback), PNG renderer, Streamlit dashboard, 43 tests green.

RULES:
- Never edit schemas.py without asking P1.
- Never edit files owned by another member (ownership map in backend/README.md).
- Never recreate files that already exist — run `git pull --rebase` FIRST.
- Keep every file under 150 lines; split if larger.
- Run existing tests before and after your changes:
  `cd backend && .venv/bin/python -m pytest tests/ -v`
- Write code with docstrings. Zero comments otherwise.
- If you don't understand something, ask me to walk you through it before changing it.
```

---

# 👨‍🔬 P2 — AI/ML Engine Prompt (Gemini + Content Quality)

## ✅ Phase 1 (DONE — keep for viva defense)

**Task 1 (done):** Gemini client live validation — `tests/test_gemini_live.py`, 5 modules, schema checks, `skipif` no key.

**Task 2 (done):** Prompt tuning — exam-focused SYSTEM_PROMPT merged to main (`bf08683`), cache schema versioning `v2`, ≥85% slides scored 4+, 0 slides scored 1.

## 🚀 Task 3: Post metadata generation — captions + hashtags (Phase 2)

```
StudyReel Phase 2 adds a publish pipeline. After a carousel is rendered,
we need Instagram-style post metadata so the content can be published to
the standalone InstaClone feed (and later real Instagram).

P1 is adding this contract to backend/app/schemas.py (do NOT edit it —
but read it once it lands):

    class PostMetadata(BaseModel):
        caption: str = Field(..., max_length=2200)
        hashtags: list[str] = Field(..., min_length=3, max_length=30)
        cover_slide: int = Field(0, ge=0)   # best slide for the cover

YOUR JOB: add `generate_post_metadata(module_name, topics) -> PostMetadata`
to backend/app/engine/post_metadata.py, following the EXACT same pattern as
gemini_client.py (same SDK, same retry/repair loop, same Pydantic-guided
output, same Ollama fallback).

Rules to encode in the prompt:
- Caption: exam-relevant, 1-3 sentences + a question or hook line + CTA.
  Must reference the module name and syllabus concepts. No emoji spam
  (max 3 emoji), no hashtags inside the caption body.
- Hashtags: max 30, from the module's actual concepts (e.g. #VTU, #CSE,
  #DataStructures, #ExamPrep, #Shorts, #Coding) + a few trending generic
  ones. No fabricated course codes.
- cover_slide: index of the strongest slide (header quality, has code).
  Rule of thumb: prefer a slide with code_block, else first slide.

Extend tests/test_gemini_live.py (or a new test_post_metadata.py) with the
same live-test pattern. Validate against REAL module output from
app/ingestion/pipeline.process_pdf on the two PDFs in examples/.

Report: pass rate, sample captions for 3 modules, and how you picked covers.
```

---

# 🎨 P3 — Rendering + InstaClone App Prompt (Jinja2/Tailwind/Playwright)

## ✅ Phase 1 (DONE — keep for viva defense)

**Task 1 (done):** `backend/app/renderer/` — templates (text/code/mixed, 1080×1350, dark theme, local woff2 fonts), `render_carousel()`, Playwright screenshots, `test_renderer.py`.

**Task 2 (done):** `tests/test_rendering_limits.py` overflow stress tests + schema edge-case unit tests.

## 🚀 Task 3: The InstaClone app — mini-Instagram feed (Phase 2)

```
Phase 2 delivers content through a STANDALONE Instagram-like app (no Meta
API — that's Phase 3). Build it in a NEW top-level folder: instaclone/

The contract between the publish pipeline and you (do NOT change it):

    POST /api/posts           body: {"post_id": str, "slides": [{"slide_number": int,
                              "image_path": str, "header": str}], "caption": str,
                              "hashtags": [str], "cover_slide": int}
                              -> 200 {"media_id": str, "feed_url": str}
    POST /api/posts/{media_id}/interact   body: {"action": "like" | "view"}
                              -> 200 {"likes": int, "views": int}
    GET  /api/feed            -> list of posts (latest first) with like/view counts

P1's Publisher (backend/app/publisher/instaclone.py) will CALL your API —
you own instaclone/, P1 owns the publisher. Do not build both.

YOUR JOB:
1. instaclone/app.py — FastAPI server on port 8100 with the 3 endpoints
   above. Storage: simple JSON file (instaclone/data/posts.json). No DB.
2. instaclone/feed.html — an Instagram-style feed page: dark UI, each post
   is a carousel card (cover slide shown first, click to cycle through
   slides), caption + hashtags below (hashtags highlighted cyan), like
   button with live count, view counter. Reuse the brand: Inter font,
   same dark palette as the renderer templates.
3. Serve feed.html at GET /feed (auto-refresh every 10s via fetch()).
4. instaclone/tests/test_instaclone.py — API tests: create post, like it,
   verify feed ordering and counts. Use FastAPI TestClient, no browser.

Run it: `cd instaclone && python -m uvicorn app:app --port 8100`
(The backend publisher talks to http://127.0.0.1:8100 — keep that default.)

You may reuse PNGs from backend/renders/ for manual testing. Keep files
under 150 lines each. This app is the DEMO CENTERPIECE — make it look good.
```

---

# 📊 P4 — Dashboard + Publish Queue Prompt (Streamlit/UI)

## ✅ Phase 1 (DONE — keep for viva defense)

**Task 1 (done):** `dashboard/studyreel_dashboard.py` — ingestion, HITL review, carousel preview + ZIP export, wired to live backend.

**Task 2 (done):** `docs/` — API.md, SETUP.md, SPRINT_LOG.md maintained; meeting minutes.

## 🚀 Task 3: Publish Queue UI + simulated account (Phase 2)

```
Phase 2 lets the dashboard PUBLISH rendered carousels to the standalone
InstaClone feed (mini-Instagram, Phase 3 will swap to real Meta API).

P1 is adding these v2 endpoints to backend/app/main.py (do NOT recreate):
    POST /api/v2/publish      body: {"carousel_id": int, "caption": str,
                              "hashtags": [str], "schedule_at": str|null}
                              -> 200 {"media_id": str, "feed_url": str, "status": "queued"|"published"}
    GET  /api/v2/posts        -> list of published posts with status
    POST /api/v2/oauth/connect   -> 200 {"token": str, "expires_at": str}  (SIMULATED)
    POST /api/v2/oauth/revoke    -> 200

YOUR JOB — extend dashboard/studyreel_dashboard.py (keep under 350 lines
total; move helpers to dashboard/api_client.py):
1. NEW "🚀 Publish" tab:
   - After a carousel renders, a caption text area (pre-filled with a
     template: module name + CTA), hashtag input, and "Publish Now" /
     "Schedule" (datetime input) buttons.
   - Call POST /api/v2/publish; show status chip: queued → published →
     LINK to the InstaClone feed (st.markdown link to /feed).
   - GET /api/v2/posts table: post_id, caption preview, status, likes,
     views, feed link. Poll every 5s while any post is "queued".
2. "🔗 Connect Account" section in the sidebar:
   - "Connect (Simulated)" button → POST /api/v2/oauth/connect → show
     token + expiry countdown. "Revoke" button → revoke. This proves the
     OAuth UX without Meta approval.
3. Keep existing tabs working. Ask P1 about /api/v2 response shapes
   before hardcoding field names.

Docs task: update docs/API.md with the v2 endpoints and docs/SPRINT_LOG.md
with the Phase 2 kickoff decision (standalone InstaClone, then Meta).
```

---

## ⚡ Force Multipliers (all members)

| Habit | Why |
|-------|-----|
| Run tests before AND after each change | Catches contract breaks instantly |
| Ask your AI for the SIMPLEST version first | Then add complexity only when needed |
| Keep prompts in a `prompts/` folder in the repo | Reproducible, so you can re-tune later |
| Commit with one clear `git commit -m` per task | P1 reviews diffs, not volumes |
| If your AI produces >150 lines, split it | Better context in the next session |

---

## ⚠️ Coordination Guardrails (Phase 2 edition)

1. **schemas.py = no-go zone** unless P1 approves. `PostMetadata` is P1's addition — read it, don't edit it.
2. **P1 owns `backend/app/publisher/`** (Publisher protocol + InstaClonePublisher + Instagram stub). P3 owns `instaclone/`. The HTTP contract above is the handshake — never change it unilaterally.
3. **P2 and P3 integrate at the caption + carousel boundary**: P2's `PostMetadata` feeds P3's feed post; `cover_slide` decides the cover.
4. **P4's dashboard polls `/api/v1/status` AND `/api/v2/posts`** — P1 keeps those endpoints stable; add fields, never remove.
5. **Ports:** backend 8000 (FastAPI), InstaClone 8100, dashboard 8501 (Streamlit). Never guess each other's ports.
6. **Conflicts in git:** each member only touches their layer; `git pull --rebase` before every push. P3: `instaclone/` is YOURS alone.
7. **Phase 3 (not yet):** swap `PUBLISHER=instaclone` → `PUBLISHER=instagram` in backend/.env. The Publisher interface makes this a config change, not a rewrite — keep your code behind the interface.
8. **If your AI tool gets stuck on the same problem twice** → screenshot/describe to P1 in a shared channel; don't silently brute-force it.