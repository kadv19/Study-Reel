# StudyReel — Card Catalog, not a Feed

**Learn to scroll.** Turn any syllabus PDF (VTU or global) into swipeable 1080×1350 study cards. Flashcards meet Reels, but calm and exam-focused.

> Upload PDF → Gemini makes bite cards → you review → Render → auto-publishes to your private shelves. Global trending seeds (AI/EV/Aero) show before you upload.

---

## 30-sec Quick Start (PC as server)

```bash
git clone https://github.com/kadv19/Study-Reel.git
cd Study-Reel
chmod +x run.sh
./run.sh
# Backend 8000 | InstaClone 8100 | Dashboard 8501
# Backend: http://127.0.0.1:8000/docs
# Deck:    http://127.0.0.1:8100/deck  (also / and /feed)
# Cabinet: http://127.0.0.1:8100/cabinet
# Dashboard: http://127.0.0.1:8501
```

**Docker:**
```bash
docker compose up --build
```

Test: `cd backend && .venv/bin/python -m pytest tests/ -v` → 64 green (53+7+4)

---

## What It Does

- **Syllabus → cards:** `pdfplumber` boundary + noise clean → `gemini-3.6-flash` (failover 5 models + Ollama `qwen2.5:7b`) generates `MicroTopic` (header ≤30, body ≤140, code ≤22×62, back_header 30/back_body 140/exam_weight low/med/high) → HITL edit → Playwright renders PNGs.
- **Deck:** book-spine shelves (fill = mastered/total), stack of 3 cards peek, 3D flip front/back, drag left=Review amber, down=Catalog cyan, right=Got it green (display `Got it`, enum `mastered`). `100dvh`, 44px targets, haptics.
- **Cabinet:** 3 drawers Review/Catalog/Got it (accordion), per-user `user_card_states` (anon → pseudo `name/college/email` via `POST /api/v1/users`, 3-dismiss onboarding).
- **Feed:** legacy global trending `likes*0.7+views*0.15-hours*0.08` kept at `/feed_legacy`, Deck is primary.
- **Publisher seam:** `PUBLISHER=instaclone` (port 8100 copy) today, `instagram` tomorrow via env only.

---

## Project Structure

```
backend/        # FastAPI 0.3.0 — /api/v1 health/status/upload/topics/render/export + /api/v1 shelves/deck/file/cabinet + /api/v1 users/colleges + /api/v2 publish/oauth/preview
instaclone/     # Deck (8100/deck) + Cabinet (8100/cabinet) + legacy feed — PWA manifest + sw.js
dashboard/      # Streamlit 8501 — Ingestion → HITL (back_* live counters) → Preview (tailored) → Publish
seed/           # 8 discovery posts (AI/EV/Aero) + generate/seed scripts
UI_UX/          # Handoff PDF + 3 html mocks (deck/cabinet/feed)
docs/           # API.md, SETUP.md, SPRINT_LOG.md, ANDROID.md
capacitor.config.json # -> Android APK sideload
```

---

## Documentation

- [docs/SETUP.md](docs/SETUP.md) — one-command + docker + LAN vs ngrok + PWA
- [docs/API.md](docs/API.md) — all endpoints + schemas + curl
- [docs/SPRINT_LOG.md](docs/SPRINT_LOG.md) — sprints + meetings
- [docs/ANDROID.md](docs/ANDROID.md) — PWA Add-to-Home + Capacitor `assembleDebug` + `adb install`
- [backend/README.md](backend/README.md) — backend-only quick start

---

## Data Flow

```
PDF upload → process_pdf → modules → Gemini MicroTopic[] → HITL back_* → render_carousel (PNG) → save_carousel → POST /api/v2/publish (copy PNGs → instaclone/data/slides/{id}/) → shelves (per-user) → deck (unfiled+review) → file {review|catalog|mastered} → cabinet
```

---

## Status

- **Done:** Ingestion, Gemini+Ollama, render (6/6), publisher 60/60, deck/cabinet (PWA), pseudo accounts, docker/run.sh, 8 seeds.
- **Next:** Real Instagram (`RENDER_CDN_URL` + status poll), spaced repetition, Ask-this-slide, per-user tailoring weight.

**Stack:** Python 3.12, FastAPI, SQLite (`studyreel.db` + `studyreel_publisher.db`), pdfplumber, google-genai, Playwright, Pillow, Pygments, Streamlit, JS pointer events.

**Ownership:** Schemas P1, Ingestion P1, Gemini P2, Renderer P3, Dashboard P4 — see `backend/README.md` map.
