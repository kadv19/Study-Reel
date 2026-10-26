"""Tests for Card Catalog API — shelves/deck/file/cabinet (PDF §4)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import MicroTopic

def test_microtopic_back_fields_optional():
    t = MicroTopic(header="Front", body="Front body")
    assert t.back_header is None
    t2 = MicroTopic(header="H", body="B", back_header="Why", back_body="Because", exam_weight="high")
    assert t2.back_header == "Why"
    assert t2.exam_weight == "high"

def test_microtopic_back_length_validation():
    with pytest.raises(Exception):
        MicroTopic(header="H", body="B", back_header="x"*31)
    with pytest.raises(Exception):
        MicroTopic(header="H", body="B", exam_weight="ultra")  # not low/medium/high

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
        MicroTopic(header="Front A", body="Body A", back_header="Back A", back_body="Back body A", exam_weight="medium"),
        MicroTopic(header="Front B", body="Body B", back_header="Back B", back_body="Back body B", exam_weight="high"),
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
