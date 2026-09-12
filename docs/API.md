# StudyReel — API Reference

This document provides complete documentation for the StudyReel REST API endpoints, request/response models, and example `curl` commands.

Base URL: `http://127.0.0.1:8000`

---

## 1. Health Check

### `GET /api/v1/health`
Checks whether the backend server is operational.

#### Request
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/health"
```

#### Response (`200 OK`)
```json
{
  "status": "ok",
  "service": "studyreel"
}
```

---

## 2. Pipeline Status

### `GET /api/v1/status`
Returns the current state, active stage, execution progress (0.0 to 1.0), and state machine message.

#### Request
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/status"
```

#### Response (`200 OK`)
```json
{
  "id": 1,
  "state": "DONE",
  "stage": "ingestion",
  "progress": 1.0,
  "message": "Extracted 5 modules (id=1)",
  "updated_at": "2026-08-14T09:11:59.633609+00:00"
}
```

#### Pipeline States
| State | Description |
|---|---|
| `IDLE` | No pipeline job currently running |
| `PROCESSING` | Ingestion, generation, or rendering in progress |
| `DONE` | Pipeline stage finished successfully |
| `FAILED` | An error occurred during processing |
| `NEEDS_SUPERVISION` | HITL review required before rendering |

---

## 3. Syllabus PDF Upload & Ingestion

### `POST /api/v1/syllabus/upload`
Uploads a syllabus PDF file, parses modules via boundary detection, removes academic noise (e.g., ISBNs, Course Outcomes, credits), stores extracted data in SQLite, and returns structured modules.

#### Request
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/syllabus/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/syllabus.pdf;type=application/pdf"
```

#### Response (`200 OK`)
```json
{
  "file_name": "syllabus.pdf",
  "total_pages": 3,
  "modules": [
    {
      "module_number": 1,
      "module_title": "Introduction to Parallel Computing",
      "topic_strings": [
        "Motivating Parallelism, Scope of Parallel Computing",
        "Parallel Programming Platforms: Implicit Parallelism"
      ]
    },
    {
      "module_number": 2,
      "module_title": "Principles of Parallel Algorithm Design",
      "topic_strings": [
        "Decomposition Techniques, Mapping Techniques for Load Balancing",
        "Methods for Containing Interaction Overheads"
      ]
    }
  ]
}
```

#### Error Response (`400 Bad Request` / `422 Unprocessable Entity`)
```json
{
  "detail": "Only PDF files are supported"
}
```

---

## 4. Module Topics (AI Generation)

### `GET /api/v1/modules/{module_number}/topics`
Generates AI micro-topics for a stored module via the Gemini engine
(gemini-3.6-flash). Requires a syllabus upload first. Drives pipeline
state: `PROCESSING -> DONE` (or `FAILED`).

#### Request
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/modules/1/topics"
```

#### Response (`200 OK`)
```json
[
  {
    "header": "HTML Document Structure",
    "body": "Every standard HTML5 document requires a DOCTYPE declaration...",
    "code_block": "<!DOCTYPE html>\n<html>...",
    "language_tag": "html"
  }
]
```

#### Errors
- `404` — module not found (upload a syllabus first)
- `502` — Gemini generation failed (check `/api/v1/status` for details)

---

## 5. Carousel Rendering & Export

### `POST /api/v1/carousels/render`
Renders approved (post-HITL) MicroTopics into 1080x1350 PNG slides via
headless Playwright. Max 10 topics (Instagram carousel limit).

#### Request
```json
{
  "module_name": "Module 1: HTML & CSS",
  "subject_code": "21CS51",
  "topics": [
    {"header": "HTML Document Structure", "body": "...", "code_block": "...", "language_tag": "html"}
  ]
}
```

#### Response (`200 OK`)
```json
{
  "id": 1,
  "carousel_id": "a1b2c3d4",
  "module_name": "Module 1: HTML & CSS",
  "slide_count": 9,
  "output_dir": ".../renders/a1b2c3d4",
  "slides": ["slide_01.png", "..."]
}
```

#### Errors
- `422` — more than 10 topics, or invalid MicroTopic
- `500` — Playwright rendering failed

### `GET /api/v1/carousels/{carousel_id}/export`
Downloads the rendered carousel as a ZIP of `slide_XX.png` files.

```bash
curl -OJ "http://127.0.0.1:8000/api/v1/carousels/1/export"
```

#### Errors
- `404` — carousel not found or slides missing

---

## 7. Publish Queue — v2 API (Phase 2)

Base prefix: `/api/v2` · Port: `8000` · Publisher target: InstaClone (port `8100`)

---

### `POST /api/v2/publish`
Publish a rendered carousel immediately or schedule it for a future time.

#### Request Body (`PublishRequest`)
```json
{
  "carousel_id": 1,
  "caption": "📚 Module 1 — key concepts! 🧠\nFollow @StudyReel for more!",
  "hashtags": ["studyreel", "computerscience", "coding"],
  "schedule_at": null
}
```
> Set `schedule_at` to an ISO 8601 datetime string (e.g. `"2026-09-01T10:00:00+00:00"`) to schedule instead of publishing immediately.

#### Response (`200 OK`) — Publish Now
```json
{
  "media_id": "a1b2c3d4",
  "feed_url": "http://127.0.0.1:8100/feed",
  "status": "published",
  "provider": "instaclone"
}
```

#### Response (`200 OK`) — Scheduled
```json
{
  "media_id": null,
  "feed_url": "",
  "status": "queued",
  "provider": "instaclone"
}
```

#### Errors
- `404` — carousel not found (render it first via `POST /api/v1/carousels/render`)
- `422` — validation error (fewer than 3 hashtags, caption too long)

---

### `GET /api/v2/posts`
List all published posts, newest first.

```bash
curl -X GET "http://127.0.0.1:8000/api/v2/posts"
```

#### Response (`200 OK`)
```json
[
  {
    "id": 1,
    "provider": "instaclone",
    "media_id": "a1b2c3d4",
    "carousel_id": 1,
    "caption": "📚 Module 1 — key concepts!",
    "hashtags": "[\"studyreel\", \"coding\"]",
    "feed_url": "http://127.0.0.1:8100/feed",
    "published_at": "2026-08-29T09:15:00+00:00"
  }
]
```

---

### `GET /api/v2/status`
Publisher health check — provider name, OAuth connection state, and total posts published.

```bash
curl -X GET "http://127.0.0.1:8000/api/v2/status"
```

#### Response (`200 OK`)
```json
{
  "provider": "instaclone",
  "oauth_connected": true,
  "posts_published": 3
}
```

---

### `POST /api/v2/oauth/connect`
Simulated OAuth handshake — generates a token without requiring Meta app approval. Token lifetime: **60 days**.

```bash
curl -X POST "http://127.0.0.1:8000/api/v2/oauth/connect"
```

#### Response (`200 OK`)
```json
{
  "token": "d4e5f6a7b8c9...",
  "expires_at": "2026-10-28T09:15:00+00:00"
}
```

---

### `POST /api/v2/oauth/revoke`
Revoke the active OAuth token.

```bash
curl -X POST "http://127.0.0.1:8000/api/v2/oauth/revoke"
```

#### Response (`200 OK`)
```json
{
  "status": "revoked",
  "connected": false
}
```

> [!NOTE]
> Phase 3 will swap `PUBLISHER=instaclone` → `PUBLISHER=instagram` in `backend/.env`.
> The Publisher interface makes this a **config change only** — no API contract changes.

---

## 7b. Tailored Metadata Preview — v2

### `POST /api/v2/metadata/preview`
Preview tailored caption/hashtags/cover without publishing. Used by Deck auto-publish and dashboard `✨ Generate`.

```bash
curl -X POST "http://127.0.0.1:8000/api/v2/metadata/preview" \
  -H "Content-Type: application/json" \
  -d '{"module_name":"OS — Module 3","topics":[{"header":"Round Robin","body":"Body","code_block":null,"language_tag":null}]}'
```

#### Response (`200 OK`)
```json
{
  "caption": "Are you ready to master Round Robin for OS exam? Save this carousel!",
  "hashtags": ["os","roundrobin","vtu","exam","studyreel"],
  "cover_slide": 0
}
```

---

## 7c. Card Catalog API — v1 (Deck/Cabinet)

Per-user filing via `X-User-Id` header (pseudo `anon-xxxx` or real `uuid` from `/api/v1/users`). Shelf fill = `mastered/total`.

### `GET /api/v1/colleges`
List clean college codes for dropdown.
```bash
curl http://127.0.0.1:8000/api/v1/colleges
# [{"code":"vtu_belgaum","label":"VTU Belgaum"}, ...]
```

### `POST /api/v1/users`
Idempotent pseudo account (C, no password). Same `email` returns same `id`, updates `name/college`.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/users -H "Content-Type: application/json" \
  -d '{"name":"Advaith","email":"a@test.com","college":"vtu_belgaum"}'
# {"id":"uuid...","name":"Advaith","email":"a@test.com","college":"vtu_belgaum",...}
```

### `GET /api/v1/users/{id}`
Fetch user profile.

### `POST /api/v1/users/migrate`
Migrate `anon` cards to real id after onboarding.
```bash
curl -X POST http://127.0.0.1:8000/api/v1/users/migrate -H "Content-Type: application/json" \
  -d '{"from_id":"anon-abc","to_id":"uuid-xyz"}'
# {"migrated": 3}
```

### `GET /api/v1/shelves`
List shelves (per carousel) with fill `mastered/total`.
```bash
curl -H "X-User-Id: anon-abc" http://127.0.0.1:8000/api/v1/shelves
# [{"shelf_id":"42","label":"OS","module_name":"OS — Module 3","carousel_id":42,"total_slides":3,"mastered_count":1,"fill_pct":0.33}]
```

### `GET /api/v1/deck?shelf=42`
Unfiled + review (catalog/mastered hidden, review resurfaces at tail).

### `POST /api/v1/file`
File a card: `left=review amber, down=catalog cyan, right=mastered (display Got it) green`.
```bash
curl -X POST http://127.0.0.1:8000/api/v1/file -H "X-User-Id: anon-abc" -H "Content-Type: application/json" \
  -d '{"post_id":"42","slide_index":0,"status":"mastered"}'
# {"card_key":"42:0","status":"mastered","shelf_fill":0.33}
```

### `GET /api/v1/cabinet?tray=review|catalog|mastered`
List filed cards per tray, most recent first.

---

## 8. Core Data Schemas

### `MicroTopic`
| Field | Type | Rules / Constraints |
|---|---|---|
| `header` | `str` | Max 30 characters |
| `body` | `str` | Max 140 characters |
| `code_block` | `Optional[str]` | Max 22 lines, max 62 chars per line |
| `language_tag` | `Optional[str]` | Whitelisted: `python`, `java`, `cpp`, `c`, `js`, `sql`, `kotlin`, `go`, `bash`, `html`, `css` |
| `back_header` | `Optional[str]` | Max 30, back side prompt e.g. `Why it matters` |
| `back_body` | `Optional[str]` | Max 140, exam relevance |
| `exam_weight` | `Optional["low"\|"medium"\|"high"]` | Exam weight, drives dots + shelf fill tie-breaker |

### `Slide`
| Field | Type | Description |
|---|---|---|
| `slide_type` | `"text" \| "code" \| "mixed"` | Template selection |
| `index` | `int` | Sequential 0-indexed position |
| `topic` | `MicroTopic` | Content chunk |

### `Carousel`
| Field | Type | Description |
|---|---|---|
| `carousel_id` | `str` | Unique carousel identifier |
| `module_name` | `str` | Max 60 characters |
| `subject_code` | `Optional[str]` | Max 20 characters |
| `slides` | `list[Slide]` | Between 1 and 10 slides in strict sequential order |

### `PublishRequest` (v2)
| Field | Type | Rules |
|---|---|---|
| `carousel_id` | `int` | Row ID from the render endpoint |
| `caption` | `str` | Max 2 200 characters |
| `hashtags` | `list[str]` | 0–30 items; auto-lowercased, `#` stripped |
| `cover_slide` | `int` | Cover index, ge 0 (tailored) |
| `schedule_at` | `Optional[str]` | ISO 8601 datetime; `null` = publish immediately |

### `UserCreate` / `UserOut` (v1 pseudo, C)
| Field | Type | Rules |
|---|---|---|
| `name` | `str` | 1-60 |
| `email` | `str` | must contain @, lowercased, unique |
| `college` | `str` | Must be `vtu_belgaum/bmsce/rvce/pes_university/msrit/dsce/other` (dropdown only) |

### `FileCardRequest` (v1)
| Field | Type | Rules |
|---|---|---|
| `post_id` | `str` | Carousel id (`carousel_id` as string) |
| `slide_index` | `int` | ge 0, < total_slides |
| `status` | `"review"\|"catalog"\|"mastered"` | Filing tray; mastered display `Got it` |

### `PostMetadata` (v2, owned by P1/P2)
| Field | Type | Rules |
|---|---|---|
| `caption` | `str` | Max 2 200 characters — hook + body + CTA |
| `hashtags` | `list[str]` | 3–30 items derived from module concepts |
| `cover_slide` | `int` | Index of the strongest slide to use as cover |
