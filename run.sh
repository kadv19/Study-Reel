#!/usr/bin/env bash
# StudyReel one-command run — backend 8000, instaclone 8100, dashboard 8501
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "== StudyReel smooth run =="

# 1. Seed discovery feed if empty (global trending before user upload)
if [ ! -f "$ROOT/instaclone/data/posts.json" ] || [ "$(cat "$ROOT/instaclone/data/posts.json" | tr -d ' \n' )" = "[]" ]; then
  echo "Seeding 8 discovery posts (AI/EV/Aero/CS)..."
  python3 "$ROOT/seed/seed_insta.py" || python "$ROOT/seed/seed_insta.py" || echo "seed skipped"
else
  echo "Seed exists: $(python3 -c "import json; print(len(json.load(open('$ROOT/instaclone/data/posts.json'))))" 2>/dev/null) posts"
fi

# 2. Ensure backend venv and deps
if [ ! -d "$ROOT/backend/.venv" ]; then
  echo "Creating backend venv..."
  python3 -m venv "$ROOT/backend/.venv"
  "$ROOT/backend/.venv/bin/pip" install -q -r "$ROOT/backend/requirements.txt"
  "$ROOT/backend/.venv/bin/playwright" install chromium || true
fi

# 3. Copy .env if missing
if [ ! -f "$ROOT/backend/.env" ]; then
  cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
  echo "Created backend/.env from example — set GEMINI_API_KEY"
fi

# 4. Start services
echo "Starting backend (8000)..."
nohup "$ROOT/backend/.venv/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir "$ROOT/backend" > /tmp/studyreel_backend.log 2>&1 &
echo $! > /tmp/studyreel_backend.pid
sleep 3
curl -s http://127.0.0.1:8000/api/v1/health | grep -q ok && echo "✅ Backend 8000" || echo "⚠️ Backend failed — see /tmp/studyreel_backend.log"

echo "Starting instaclone (8100)..."
nohup "$ROOT/backend/.venv/bin/python" -m uvicorn instaclone.app:app --host 127.0.0.1 --port 8100 --app-dir "$ROOT" > /tmp/studyreel_instaclone.log 2>&1 &
echo $! > /tmp/studyreel_instaclone.pid
sleep 2
curl -s http://127.0.0.1:8100/api/feed | grep -q posts && echo "✅ InstaClone 8100" || echo "⚠️ InstaClone failed — see /tmp/studyreel_instaclone.log"

echo "Starting dashboard (8501)..."
# Use backend venv for streamlit if dashboard venv missing
VENV="$ROOT/backend/.venv"
if [ -d "$ROOT/dashboard/.venv" ]; then VENV="$ROOT/dashboard/.venv"; fi
nohup "$VENV/bin/streamlit" run "$ROOT/dashboard/studyreel_dashboard.py" --server.port 8501 --server.address 127.0.0.1 > /tmp/studyreel_dashboard.log 2>&1 &
echo $! > /tmp/studyreel_dashboard.pid
sleep 3
echo "✅ Dashboard 8501"

echo ""
echo "== All up =="
echo "Backend:   http://127.0.0.1:8000/docs"
echo "InstaClone: http://127.0.0.1:8100/feed  (trending global, filter chips)"
echo "Dashboard: http://127.0.0.1:8501  (syllabus → auto-publish → feed-first, download optional)"
echo ""
echo "Download: render in dashboard → ZIP (optional) — feed-first, offline when you want"
echo "Logs: /tmp/studyreel_backend.log /tmp/studyreel_instaclone.log /tmp/studyreel_dashboard.log"
echo "Stop: kill \$(cat /tmp/studyreel_*.pid)  or  pkill -f uvicorn; pkill -f streamlit"
