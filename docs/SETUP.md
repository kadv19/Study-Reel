# StudyReel — Environment Setup Guide

This guide walks through setting up the complete StudyReel development environment on a fresh laptop (Windows, macOS, or Linux).

---

## 1. Prerequisites

- **Python**: Version 3.11, 3.12, or 3.13
- **Git**: For cloning and version control
- **Google Gemini API Key**: (Required for Sprint 2 AI generation layer — fallback template works without it)
- **Ports free**: `8000` backend, `8100` InstaClone feed, `8501` dashboard

---

## 2. Clone the Repository

```bash
git clone https://github.com/kadv19/Study-Reel.git
cd Study-Reel
```

---

## 3. Backend Setup

### A. Create and Activate Virtual Environment

**Windows (PowerShell):**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

### B. Install Dependencies

```bash
pip install -r requirements.txt
```

### C. Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` in your editor and configure your variables:
```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
LOG_LEVEL=INFO
```

### D. Install Playwright Browser Binaries (for Sprint 3 Renderer)

Playwright requires its dedicated Chromium binary:
```bash
python -m playwright install chromium
```

---

## 4. Admin Dashboard Setup (Streamlit)

You can run the dashboard using the backend venv or create a dedicated venv under `dashboard/`:

```bash
cd dashboard
pip install -r requirements.txt
```

---

## 5. Running the Application — One Command

### Fastest: `./run.sh` (smooth, recommended)
From repo root:
```bash
chmod +x run.sh
./run.sh
```
- Seeds 8 discovery posts if `instaclone/data/posts.json` empty (AI/EV/Aero/CS trending)
- Starts backend `8000`, InstaClone `8100`, dashboard `8501`
- **Backend**: `http://127.0.0.1:8000/docs` — health `GET /api/v1/health`
- **InstaClone Feed**: `http://127.0.0.1:8100/feed` — global trending (`?sort=trending|newest&tag=ai|ev|aerodynamics`), no per-user memory, auto-refresh 10s, swipe + filter chips
- **Dashboard**: `http://127.0.0.1:8501` — syllabus PDF → Generate → Review → Render (auto-publishes to feed) — **feed-first**, download is optional `⬇️ ZIP` / `JSON`
- Logs: `/tmp/studyreel_backend.log`, `/tmp/studyreel_instaclone.log`, `/tmp/studyreel_dashboard.log`
- Stop: `kill $(cat /tmp/studyreel_*.pid)` or `pkill -f uvicorn; pkill -f streamlit`

### Docker (downloadable, reproducible)
```bash
docker compose up --build
```
- Uses `backend/Dockerfile`, `instaclone/Dockerfile`, `dashboard/Dockerfile`
- Same ports `8000/8100/8501`, env `INSTACLONE_URL` auto-wired

### Manual (step-by-step)
```bash
# Backend
cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# InstaClone (separate terminal, repo root)
uvicorn instaclone.app:app --host 127.0.0.1 --port 8100 --app-dir .
# Dashboard (repo root)
streamlit run dashboard/studyreel_dashboard.py --server.port 8501
# Seed if needed
python seed/seed_insta.py
```

---

## 6. Download — Feed-First, Offline When You Want
- **Primary:** after `Render` (auto-publish ✅) images live in feed `http://127.0.0.1:8100/feed` — scroll instead of Instagram, like/view counts, trending `likes*0.7+views*0.15`
- **Secondary (on-demand):** `Carousel Preview & Export` → `⬇️ Download Carousel ZIP` or `📄 Export Topics JSON` — only when you ask

## 7. Running Tests

From `backend/`:
```bash
pytest tests/ -v                 # 53 backend (76s)
PYTHONPATH=.:backend pytest ../instaclone/tests -v  # 7 instaclone
```

> [!NOTE]
> `60/60 green` required (53+7). Before/after every change. Live `GEMINI_API_KEY` needed for 8 live tests else skipped → 45.
