# StudyReel — Environment Setup Guide

This guide walks through setting up the complete StudyReel development environment on a fresh laptop (Windows, macOS, or Linux).

---

## 1. Prerequisites

- **Python**: Version 3.11, 3.12, or 3.13
- **Git**: For cloning and version control
- **Google Gemini API Key**: (Required for Sprint 2 AI generation layer)

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

## 5. Running the Application

### A. Start the Backend API (FastAPI)

From the `backend/` directory:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- **API Base URL**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

### B. Launch the Admin Dashboard (Streamlit)

From the repo root or `dashboard/`:
```bash
streamlit run dashboard/studyreel_dashboard.py
```
- **Dashboard URL**: `http://localhost:8501`

---

## 6. Running Tests

StudyReel uses `pytest` to maintain strict contract validation:

From `backend/`:
```bash
pytest tests/ -v
```

> [!NOTE]
> All 25 baseline test cases must stay green before and after making any modifications.
