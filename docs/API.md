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

## 5. Upcoming Sprint 4 Endpoints (Planned)

### `POST /api/v1/carousels/generate`
Triggers Gemini micro-topic generation for extracted modules.

### `GET /api/v1/carousels/{carousel_id}/export`
Downloads a packaged ZIP archive containing rendered 1080x1350 PNG slides.

---

## 6. Core Data Schemas

### `MicroTopic`
| Field | Type | Rules / Constraints |
|---|---|---|
| `header` | `str` | Max 30 characters |
| `body` | `str` | Max 140 characters |
| `code_block` | `Optional[str]` | Max 22 lines, max 62 chars per line |
| `language_tag` | `Optional[str]` | Whitelisted: `python`, `java`, `cpp`, `c`, `js`, `sql`, `kotlin`, `go`, `bash`, `html`, `css` |

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
