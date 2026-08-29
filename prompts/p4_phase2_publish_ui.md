# P4 Phase 2 — Dashboard Publish Queue UI Prompt

> Stored per guardrail: "Keep prompts in a `prompts/` folder in the repo, Reproducible, so you can re-tune later"

## Source
TEAM_PROMPTS.md — P4 section, Phase 2

## Prompt (verbatim)

```
P4 — Dashboard + Publish Queue Prompt (Streamlit/UI)

Phase 1 (DONE — keep for viva defense)
Task 1 (done): dashboard/studyreel_dashboard.py — ingestion, HITL review, carousel preview + ZIP export, wired to live backend.
Task 2 (done): docs/ — API.md, SETUP.md, SPRINT_LOG.md maintained; meeting minutes.

Task 3: Publish Queue UI + simulated account (Phase 2)

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
1. NEW "?? Publish" tab:
   - After a carousel renders, a caption text area (pre-filled with a
     template: module name + CTA), hashtag input, and "Publish Now" /
     "Schedule" (datetime input) buttons.
   - Call POST /api/v2/publish; show status chip: queued ? published ?
     LINK to the InstaClone feed (st.markdown link to /feed).
   - GET /api/v2/posts table: post_id, caption preview, status, likes,
     views, feed link. Poll every 5s while any post is "queued".
2. "?? Connect Account" section in the sidebar:
   - "Connect (Simulated)" button ? POST /api/v2/oauth/connect ? show
     token + expiry countdown. "Revoke" button ? revoke. This proves the
     OAuth UX without Meta approval.
3. Keep existing tabs working. Ask P1 about /api/v2 response shapes
   before hardcoding field names.

Docs task: update docs/API.md with the v2 endpoints and docs/SPRINT_LOG.md
with the Phase 2 kickoff decision (standalone InstaClone, then Meta).
```

## What was actually built

| Deliverable | File | Notes |
|---|---|---|
| Publish tab | `dashboard/studyreel_dashboard.py` | 317 lines total (=350 guardrail) |
| v2 API helpers | `dashboard/api_client.py` | 5 new functions |
| API docs | `docs/API.md` | Section 7 replaced with full v2 docs |
| Sprint log | `docs/SPRINT_LOG.md` | Phase 2 sprint + Meeting #2 |
| This prompt | `prompts/p4_phase2_publish_ui.md` | Reproducibility record |

## Guardrails respected
- `backend/app/schemas.py` — not touched
- `backend/app/publisher/` — not touched
- Ports: backend 8000, InstaClone 8100, dashboard 8501
- Tests: 32 pass / 1 pre-existing Playwright fail (baseline maintained)
