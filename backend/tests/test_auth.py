"""Authorization regression tests: bearer tokens and cross-user isolation."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import Carousel, ExtractedModule, MicroTopic, Slide, Syllabus


@pytest.fixture
def client_ctx():
    with TestClient(app) as c:
        yield c


def _make_owned_book(owner_id: str, tmp_path) -> tuple[int, int]:
    from app.db.database import get_module, save_carousel, save_syllabus

    syllabus = Syllabus(
        file_name=f"book-{uuid.uuid4().hex[:8]}.pdf",
        total_pages=1,
        modules=[
            ExtractedModule(
                module_number=1,
                module_title="Private Module",
                topic_strings=["Private topic"],
            )
        ],
    )
    syllabus_id = save_syllabus(syllabus, owner_user_id=owner_id)
    module = get_module(1, owner_user_id=owner_id)
    topic = MicroTopic(header="Private", body="A complete explanation that states the main idea and why it matters for exams.")
    carousel = Carousel(
        carousel_id=uuid.uuid4().hex[:8],
        module_name="Private Module",
        slides=[Slide(slide_type="text", index=0, topic=topic)],
    )
    carousel_id = save_carousel(
        carousel,
        module["id"],
        output_dir=str(tmp_path / "renders" / carousel.carousel_id),
    )
    return syllabus_id, carousel_id


def test_protected_routes_require_token(client_ctx):
    assert client_ctx.get("/api/v1/status").status_code == 401
    assert client_ctx.get("/api/v1/shelves").status_code == 401
    assert client_ctx.get("/api/v1/books").status_code == 401
    assert client_ctx.get("/api/v1/library").status_code == 401
    assert client_ctx.get("/api/v1/deck?shelf=1").status_code == 401
    assert client_ctx.post(
        "/api/v1/file",
        json={"post_id": "1", "slide_index": 0, "status": "review"},
    ).status_code == 401
    assert client_ctx.get("/api/v1/cabinet?tray=review").status_code == 401
    assert client_ctx.delete("/api/v1/library/1").status_code == 401
    assert client_ctx.delete("/api/v1/books/1").status_code == 401
    assert client_ctx.delete("/api/v1/syllabi/1").status_code == 401
    assert client_ctx.get("/api/v1/modules/1/topics").status_code == 401
    assert client_ctx.post(
        "/api/v1/modules/1/topics",
        json={"depth_format": "short", "tone": "default", "slide_count": 5},
    ).status_code == 401
    assert client_ctx.post(
        "/api/v1/carousels/render",
        json={"module_name": "Module", "topics": [{"header": "H", "body": "B"}]},
    ).status_code == 401
    assert client_ctx.get("/api/v1/carousels/1/export").status_code == 401
    assert client_ctx.get("/api/v1/carousels/1/slides/0.png").status_code == 401
    assert client_ctx.get("/api/v1/auth/me").status_code == 401
    assert client_ctx.post(
        "/api/v1/syllabus/upload",
        files={"file": ("sample.pdf", b"%PDF-1.4", "application/pdf")},
    ).status_code == 401


def test_invalid_or_malformed_token_is_rejected(client_ctx):
    assert client_ctx.get(
        "/api/v1/shelves", headers={"Authorization": "Bearer not-a-real-token"}
    ).status_code == 401
    assert client_ctx.get(
        "/api/v1/shelves", headers={"Authorization": "Basic abc"}
    ).status_code == 401


def test_user_cannot_read_file_or_delete_another_users_book(
    client_ctx, make_user, tmp_path
):
    user_a, headers_a = make_user()
    user_b, headers_b = make_user()
    syllabus_id, carousel_id = _make_owned_book(user_b["id"], tmp_path)

    # A's library and shelves must not contain B's private data.
    library = client_ctx.get("/api/v1/library", headers=headers_a).json()
    assert all(str(book.get("syllabus_id")) != str(syllabus_id) for book in library)
    shelves = client_ctx.get("/api/v1/shelves", headers=headers_a).json()
    assert all(shelf.get("carousel_id") != carousel_id for shelf in shelves)

    # A cannot open the deck or file cards on B's carousel.
    assert client_ctx.get(
        f"/api/v1/deck?shelf={carousel_id}", headers=headers_a
    ).status_code in (403, 404)
    assert client_ctx.post(
        "/api/v1/file",
        json={"post_id": str(carousel_id), "slide_index": 0, "status": "mastered"},
        headers=headers_a,
    ).status_code in (403, 404)

    # A cannot read rendered assets or delete B's book.
    assert client_ctx.get(
        f"/api/v1/carousels/{carousel_id}/export", headers=headers_a
    ).status_code in (403, 404)
    assert client_ctx.get(
        f"/api/v1/carousels/{carousel_id}/slides/0.png", headers=headers_a
    ).status_code in (403, 404)
    assert client_ctx.delete(
        f"/api/v1/library/{syllabus_id}", headers=headers_a
    ).status_code in (403, 404)

    # B still has full access to their own book.
    assert client_ctx.get(
        f"/api/v1/deck?shelf={carousel_id}", headers=headers_b
    ).status_code == 200
    assert client_ctx.post(
        "/api/v1/file",
        json={"post_id": str(carousel_id), "slide_index": 0, "status": "mastered"},
        headers=headers_b,
    ).status_code == 200
    assert client_ctx.delete(
        f"/api/v1/library/{syllabus_id}", headers=headers_b
    ).status_code == 200
