# StudyReel — Exact Prompts for P2, P3, P4 (AI-Assisted Setup)

Give each teammate their copy-paste prompt. They must run these in order (Setup → Task prompts). The backend scaffold (P1's work) is already in place — **they must NOT recreate it**, only build on it.

---

## Common Setup (ALL MEMBERS — run once)

```
You are working on StudyReel, a 6-week major project. The repo is at:
{repo_path}/studyreel

First, read these files THOROUGHLY before writing any code:
1. backend/README.md — project overview and ownership map
2. backend/app/schemas.py — THE CONTRACT. Every layer builds against these types.
3. HANDOFF_OPENCLAW.md — current project state and gotchas

RULES:
- Never edit schemas.py without asking P1.
- Never recreate files that already exist.
- Keep every file under 150 lines; split if larger.
- Run existing tests before and after your changes: `cd backend && .venv/bin/python -m pytest tests/ -v`
- Write code with docstrings. Zero comments otherwise.
- If you don't understand something, ask me to walk you through it before changing it.
```

---

# 👨‍🔬 P2 — AI/ML Engine Prompt (Gemini + Content Quality)

## Task 1: Validate the Gemini client (today)

```
StudyReel backend has a Gemini client stub at backend/app/engine/gemini_client.py
that I (P1) wrote but never tested against the real API — it's YOUR job.

1. Create backend/.env from .env.example and put in your real GEMINI_API_KEY.
2. Write a test script tests/test_gemini_live.py that:
   - Calls generate_topics_for_module() with a REAL syllabus-like text
   - Assertions: returns list[MicroTopic], all fields within schema limits,
     no exception for a valid module text
3. Run it. If Gemini output fails Pydantic validation, that's EXPECTED to
   happen sometimes — investigate WHY and fix the system prompt in
   gemini_client.py (SYSTEM_PROMPT constant) until validation passes
   consistently across 5 different module texts.

KNOW THIS: the contract between engine and everything else is
MicroTopic(header≤30, body≤140, code_block optional, language_tag in whitelist).
My prompt may be too loose or too strict — tune it. Measure the validation
failure rate across 5 modules. Report: pass rate, quality issues you see.

IMPORTANT: after this works, mark your test with @pytest.mark.skipif(no key)
so the normal test suite still runs without a live API key.
```

## Task 2: Prompt engineering + quality tuning (Sprint 2)

```
You are tuning StudyReel's pedagogical prompt. Goal: Gemini 2.5 Flash must
produce micro-lessons a student can absorb in 45-60 seconds of scrolling.

Use the STUDY PDFS the team gives you (VTU CSE/ECE/ISE syllabi). For each:
1. Run ingestion (app/ingestion/pipeline.process_pdf) to get clean module text
2. Generate topics with the client
3. Manually review EVERY slide and grade it: 5=perfect exam-focused, 3=generic,
   1=hallucinated/wrong. Log grades in a markdown table.

Iterate the SYSTEM_PROMPT until ≥85% of slides score 4 or higher, and NONE
score 1. Document your final prompt and why each rule in it exists
(one line per rule) — this is your viva defense material.

Also implement the caching layer improvement: cache keyed by MD5 of the
module text (already partially in the client — make it robust to schema
changes by versioning the cache key).
```

---

# 🎨 P3 — Rendering + Tests Prompt (Jinja2/Tailwind/Playwright)

## Task 1: Carousel templates (Sprint 3)

```
StudyReel renders Instagram carousels (1080x1350 px) from MicroTopic data.
The contract is in backend/app/schemas.py — read it first.

Your job: build backend/app/renderer/ with:
1. templates/ — Jinja2 HTML templates, one per slide_type:
   - text.html (header + body, no code)
   - code.html (header + Pygments-highlighted code + caption)
   - mixed.html (shorter body above a compact code block)
   Each template: 1080x1350 fixed size, dark technical theme matching
   the brand vibe, Inter + Fira Code fonts imported from LOCAL
   static/ folder (.woff2 files — never CDN).
2. static/ — download Inter and Fira Code .woff2 and place here.
3. render.py — function render_carousel(carousel: Carousel, out_dir) that
   compiles templates with Tailwind (use standalone Tailwind CLI, NOT CDN),
   loads HTML in headless Playwright, waits for fonts+layout stability,
   screenshots each slide at device_scale_factor=2.
4. A test tests/test_renderer.py that renders a sample Carousel and
   asserts PNGs exist, are exactly 1080x1350, and non-blank.

FIRST run `cd backend && .venv/bin/python -m playwright install chromium`
(Playwright needs ITS OWN browser — system Chromium won't work).

Constraints: text must never overflow the slide (schema already caps body
at 140 chars — but wrap at ~28 chars/line with 16px font, and add
line-clamping as a belt-and-braces).
```

## Task 2: Overflow stress tests + unit tests (Sprint 3)

```
Add a stress-test suite tests/test_rendering_limits.py:
- Slide with 140-char body (max) → renders, no overflow
- Code slide with 22 lines × 62 chars (schema max) → renders
- Code slide with 1 giant word of 62 chars (no spaces) → renderer must not break layout
- Text with emoji (fonts-noto-color-emoji fallback check)
Each test: assert no horizontal scrollbar and PNG dimensions correct.

Also add unit tests for schemas.py edge cases I haven't covered:
- MicroTopic with every allowed language tag
- Carousel with exactly 10 slides (max) — what should the pipeline do?
  Liase with P1 before deciding the carve-up behaviour.
```

---

# 📊 P4 — Dashboard + Documentation Prompt (Streamlit/UI)

## Task 1: Streamlit dashboard (Sprint 4)

```
StudyReel needs an admin dashboard to upload a syllabus PDF, watch the
pipeline progress, and download the finished carousel ZIP.

The API lives at backend/app/main.py. Endpoints that exist:
- POST /api/v1/syllabus/upload (multipart PDF → Syllabus JSON)
- GET /api/v1/status (pipeline state)
More endpoints arrive in Sprint 4 (generation + carousel export) — design
your client around these.

Build dashboard/studyreel_dashboard.py (Streamlit) with:
1. st.file_uploader for the PDF
2. "Run Pipeline" button → POST to backend, poll GET /status every 2s,
   show st.progress(stages) driven by the pipeline state machine:
   IDLE→PROCESSING→DONE/FAILED
3. On DONE: display extracted module list (st.expander per module,
   show topic strings)
4. On FAILED: show the error message from the status endpoint
5. Carousel preview + ZIP download button (works when Sprint 4
   endpoints land — stub it gracefully until then)

Font/UX: dark theme to match the brand. Keep the whole file under 250 lines.

Run it: `cd backend && ../dashboard/venv/bin/streamlit run ...` — create a
venv in dashboard/ and install streamlit + requests + httpx first.
```

## Task 2: Documentation + sprint tracking (ongoing)

```
You are StudyReel's documentation owner. Maintain:
1. backend/README.md — keep the ownership map table fresh and update the
   "Status" column as each layer lands (ask P1/P2/P3 before marking done).
2. docs/ folder at repo root with:
   - SETUP.md (how a fresh laptop runs everything: venv, deps, env file)
   - API.md (every endpoint, request/response examples, with curl)
   - SPRINT_LOG.md (append-only: date, sprint, what shipped, blockers)
3. Meeting minutes: after every team meeting, summarize decisions into
   SPRINT_LOG.md within 24h.

Also build the "manual review" view in the dashboard: after generation,
before rendering, the user should be able to approve/edit each MicroTopic.
Ask P1 what the generation endpoint will return before building this —
it's the P2/P1 integration point.
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

## ⚠️ Coordination Guardrails

1. **schemas.py = no-go zone** unless P1 approves. It's the contract.
2. **P2 and P3 integrate at `generate_topics`** — P2 owns the client + prompt, P3 owns rendering. The JSON schema is the handshake.
3. **P4's dashboard polls `/api/v1/status`** — P1 keeps that endpoint stable; add fields, never remove.
4. **Conflicts in git:** each member only touches their layer; `git pull --rebase` before every push.
5. **If your AI tool gets stuck on the same problem twice** → screenshot/describe to P1 in a shared channel; don't silently brute-force it.