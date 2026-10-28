"""Tests for Card Catalog API — shelves/deck/file/cabinet (PDF §4)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import MicroTopic


def _make_carousel(tmp_path, make_user, slide_count=1):
    from pathlib import Path

    from app.db.database import get_module, save_carousel, save_syllabus
    from app.schemas import Carousel, ExtractedModule, Slide, Syllabus

    user, headers = make_user()
    uid = user["id"]
    syllabus = Syllabus(
        file_name=f"catalog-{uid[:6]}.pdf",
        total_pages=1,
        modules=[ExtractedModule(module_number=1, module_title="Catalog Mod", topic_strings=["Topic A"])],
    )
    save_syllabus(syllabus, owner_user_id=uid)
    module = get_module(1, owner_user_id=uid)
    topics = [
        MicroTopic(header=f"Front {i}", body=f"A complete explanation for card {i} that states the idea and why it matters.", back_header=f"Back {i}", back_body=f"Back body {i}")
        for i in range(slide_count)
    ]
    slides = [Slide(slide_type="text", index=i, topic=t) for i, t in enumerate(topics)]
    carousel = Carousel(carousel_id=f"catalog{uid[:6]}", module_name="Catalog Mod", slides=slides)
    out = Path(tmp_path) / "renders" / carousel.carousel_id
    out.mkdir(parents=True, exist_ok=True)
    for i in range(slide_count):
        (out / f"slide_{i + 1:02d}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    cid = save_carousel(carousel, module_id=module["id"], output_dir=str(out))
    return user, headers, cid


def test_microtopic_back_fields_optional():
    t = MicroTopic(header="Front", body="A complete explanation that states the main idea and why it matters for exams.")
    assert t.back_header is None
    t2 = MicroTopic(header="H", body="Another complete explanation that states the main idea and why it matters for exams.", back_header="Why", back_body="Because", exam_weight="high")
    assert t2.back_header == "Why"
    assert t2.exam_weight == "high"

def test_microtopic_back_length_validation():
    with pytest.raises(Exception):
        MicroTopic(header="H", body="A complete explanation that states the main idea and why it matters for exams.", back_header="x"*31)
    with pytest.raises(Exception):
        MicroTopic(header="H", body="A complete explanation that states the main idea and why it matters for exams.", exam_weight="ultra")  # not low/medium/high

def test_shelves_requires_render(tmp_path, auth_headers):
    client = TestClient(app)
    r = client.get("/api/v1/shelves", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_deck_file_cabinet_flow(tmp_path, make_user):
    from app.db.database import get_module, save_carousel, save_syllabus
    from app.schemas import Carousel, ExtractedModule, Slide, MicroTopic, Syllabus
    from pathlib import Path
    client = TestClient(app)
    user, headers = make_user()
    uid = user["id"]
    # create an owned book/module so the carousel is scoped to this user
    syllabus = Syllabus(
        file_name="catalog test.pdf",
        total_pages=1,
        modules=[ExtractedModule(module_number=1, module_title="Catalog Mod", topic_strings=["Topic A"])],
    )
    save_syllabus(syllabus, owner_user_id=uid)
    module = get_module(1, owner_user_id=uid)
    # create a carousel with 2 slides, back fields included
    topics = [
        MicroTopic(header="Front A", body="A complete explanation that states the main idea and why it matters for exams.", back_header="Back A", back_body="Back body A", exam_weight="medium"),
        MicroTopic(header="Front B", body="Another complete explanation that states the main idea and why it matters for exams.", back_header="Back B", back_body="Back body B", exam_weight="high"),
    ]
    slides = [Slide(slide_type="text", index=i, topic=t) for i, t in enumerate(topics)]
    carousel = Carousel(carousel_id="catalogtest"+uid[:3], module_name="Catalog Mod", slides=slides)
    out = Path(tmp_path) / "renders" / carousel.carousel_id
    out.mkdir(parents=True, exist_ok=True)
    for i in range(len(slides)):
        (out / f"slide_{i + 1:02d}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    cid = save_carousel(carousel, module_id=module["id"], output_dir=str(out))
    # shelves should contain this carousel
    r = client.get("/api/v1/shelves", headers=headers)
    assert r.status_code == 200
    shelves = r.json()
    assert any(s["carousel_id"] == cid for s in shelves)
    # deck should have 2 cards unfiled
    r2 = client.get(f"/api/v1/deck?shelf={cid}", headers=headers)
    assert r2.status_code == 200
    deck = r2.json()
    assert deck["shelf_id"] == str(cid)
    assert len(deck["cards"]) == 2
    assert deck["cards"][0]["front"]["header"] == "Front A"
    assert deck["cards"][0]["back"]["back_header"] == "Back A"
    # file first card as mastered
    r3 = client.post("/api/v1/file", json={"post_id": str(cid), "slide_index": 0, "status": "mastered"}, headers=headers)
    assert r3.status_code == 200
    assert r3.json()["status"] == "mastered"
    assert r3.json()["shelf_fill"] == 0.5
    # shelf fill should be 0.5 now
    r4 = client.get("/api/v1/shelves", headers=headers)
    shelf = next(s for s in r4.json() if s["carousel_id"] == cid)
    assert shelf["fill_pct"] == 0.5
    assert shelf["mastered_count"] == 1
    # deck should now have 1 card (the other unfiled) — mastered not resurfaced
    r5 = client.get(f"/api/v1/deck?shelf={cid}", headers=headers)
    assert len(r5.json()["cards"]) == 1
    assert r5.json()["cards"][0]["slide_index"] == 1
    # file second as review
    client.post("/api/v1/file", json={"post_id": str(cid), "slide_index": 1, "status": "review"}, headers=headers)
    # deck should resurface review after unfiled exhausted: we have 0 unfiled, 1 review -> deck should show review card
    r6 = client.get(f"/api/v1/deck?shelf={cid}", headers=headers)
    assert len(r6.json()["cards"]) == 1
    assert r6.json()["cards"][0]["status"] == "review"
    # cabinet should have both
    rc = client.get("/api/v1/cabinet?tray=mastered", headers=headers)
    assert rc.json()["count"] == 1
    rc2 = client.get("/api/v1/cabinet?tray=review", headers=headers)
    assert rc2.json()["count"] == 1


def test_unfile_mastered_card(tmp_path, make_user):
    from app.db.database import list_card_states

    user, headers, cid = _make_carousel(tmp_path, make_user, slide_count=2)
    client = TestClient(app)
    r = client.post(
        "/api/v1/file",
        json={"post_id": str(cid), "slide_index": 0, "status": "mastered"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["shelf_fill"] == 0.5

    r = client.post(
        "/api/v1/file",
        json={"post_id": str(cid), "slide_index": 0, "status": "unfiled"},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "unfiled"
    assert body["row"] is None
    assert body["shelf_fill"] == 0.0

    states = [s for s in list_card_states(user["id"]) if s["carousel_id"] == cid and s["slide_index"] == 0]
    assert states == []

    deck = client.get(f"/api/v1/deck?shelf={cid}", headers=headers).json()
    assert len(deck["cards"]) == 2
    assert deck["progress"] == ["unfiled", "unfiled"]


def test_unfile_review_card(tmp_path, make_user):
    from app.db.database import list_card_states

    user, headers, cid = _make_carousel(tmp_path, make_user)
    client = TestClient(app)
    r = client.post(
        "/api/v1/file",
        json={"post_id": str(cid), "slide_index": 0, "status": "review"},
        headers=headers,
    )
    assert r.status_code == 200

    r = client.post(
        "/api/v1/file",
        json={"post_id": str(cid), "slide_index": 0, "status": "unfiled"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "unfiled"
    assert r.json()["row"] is None
    assert r.json()["shelf_fill"] == 0.0

    states = [s for s in list_card_states(user["id"]) if s["carousel_id"] == cid and s["slide_index"] == 0]
    assert states == []

    deck = client.get(f"/api/v1/deck?shelf={cid}", headers=headers).json()
    assert len(deck["cards"]) == 1
    assert deck["cards"][0]["slide_index"] == 0
    assert deck["cards"][0]["status"] == "unfiled"


def test_unfile_never_filed_is_noop(tmp_path, make_user):
    _user, headers, cid = _make_carousel(tmp_path, make_user)
    client = TestClient(app)
    r = client.post(
        "/api/v1/file",
        json={"post_id": str(cid), "slide_index": 0, "status": "unfiled"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "unfiled"
    assert r.json()["row"] is None

    deck = client.get(f"/api/v1/deck?shelf={cid}", headers=headers).json()
    assert len(deck["cards"]) == 1
    assert deck["cards"][0]["status"] == "unfiled"
    assert deck["progress"] == ["unfiled"]


def test_unfile_does_not_touch_other_users_state(tmp_path, make_user):
    from app.db.database import list_card_states, upsert_card_state

    _user_a, headers_a, cid = _make_carousel(tmp_path, make_user)
    user_b, _headers_b = make_user()
    upsert_card_state(user_b["id"], cid, 0, "mastered")
    client = TestClient(app)

    r = client.post(
        "/api/v1/file",
        json={"post_id": str(cid), "slide_index": 0, "status": "unfiled"},
        headers=headers_a,
    )
    assert r.status_code == 200

    b_states = [s for s in list_card_states(user_b["id"]) if s["carousel_id"] == cid and s["slide_index"] == 0]
    assert len(b_states) == 1
    assert b_states[0]["status"] == "mastered"


def test_deck_progress_length_and_catalog_mapping(tmp_path, make_user):
    from app.db.database import upsert_card_state

    user, headers, cid = _make_carousel(tmp_path, make_user, slide_count=3)
    upsert_card_state(user["id"], cid, 0, "mastered")
    upsert_card_state(user["id"], cid, 1, "catalog")
    upsert_card_state(user["id"], cid, 2, "review")
    client = TestClient(app)

    deck = client.get(f"/api/v1/deck?shelf={cid}", headers=headers).json()
    assert len(deck["progress"]) == deck["total_slides"] == 3
    assert deck["progress"] == ["mastered", "review", "review"]

    replay = client.get(f"/api/v1/deck?shelf={cid}&replay=true", headers=headers).json()
    assert len(replay["progress"]) == 3
    assert replay["progress"] == ["mastered", "review", "review"]


def test_report_card_stores_report(make_user):
    from app.db.database import _connect

    user, headers = make_user()
    client = TestClient(app)
    r = client.post(
        "/api/v1/report",
        json={"card_id": "123:0", "user_id": user["id"], "reason": "Wrong formula"},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["reported"] is True
    assert data["card_id"] == "123:0"
    assert data["user_id"] == user["id"]
    assert data["reason"] == "Wrong formula"
    assert data["created_at"]

    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT card_id, user_id, reason FROM card_reports WHERE id=%s",
            (data["id"],),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    assert dict(row) == {"card_id": "123:0", "user_id": user["id"], "reason": "Wrong formula"}


def test_report_card_requires_auth():
    client = TestClient(app)
    r = client.post("/api/v1/report", json={"card_id": "123:0", "reason": "Wrong"})
    assert r.status_code == 401


def test_file_rejects_catalog(tmp_path, make_user):
    _user, headers, cid = _make_carousel(tmp_path, make_user)
    client = TestClient(app)
    r = client.post(
        "/api/v1/file",
        json={"post_id": str(cid), "slide_index": 0, "status": "catalog"},
        headers=headers,
    )
    assert r.status_code == 422


def test_existing_catalog_rows_read_as_review(tmp_path, make_user):
    from app.db.database import upsert_card_state

    user, headers, cid = _make_carousel(tmp_path, make_user)
    upsert_card_state(user["id"], cid, 0, "catalog")
    client = TestClient(app)

    deck = client.get(f"/api/v1/deck?shelf={cid}", headers=headers).json()
    assert len(deck["cards"]) == 1
    assert deck["cards"][0]["status"] == "review"

    cabinet = client.get("/api/v1/cabinet?tray=review", headers=headers).json()
    assert cabinet["count"] == 1
    assert cabinet["cards"][0]["status"] == "review"

    assert client.get("/api/v1/cabinet?tray=catalog", headers=headers).status_code == 400
