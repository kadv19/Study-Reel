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

def test_shelves_requires_render(tmp_path, monkeypatch):
    import uuid
    from app.db.database import init_db
    # use isolated DB? but we use main DB; just check endpoint returns list
    client = TestClient(app)
    r = client.get("/api/v1/shelves", headers={"X-User-Id": f"test-user-{uuid.uuid4().hex[:4]}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_deck_file_cabinet_flow(tmp_path):
    import uuid
    from app.db.database import save_carousel, init_db
    from app.schemas import Carousel, Slide, MicroTopic
    from app.renderer.render import render_carousel
    from pathlib import Path
    client = TestClient(app)
    uid = f"test-catalog-{uuid.uuid4().hex[:6]}"
    # create a carousel with 2 slides, back fields included
    topics = [
        MicroTopic(header="Front A", body="Body A", back_header="Back A", back_body="Back body A", exam_weight="medium"),
        MicroTopic(header="Front B", body="Body B", back_header="Back B", back_body="Back body B", exam_weight="high"),
    ]
    slides = [Slide(slide_type="text", index=i, topic=t) for i, t in enumerate(topics)]
    carousel = Carousel(carousel_id="catalogtest"+uid[:3], module_name="Catalog Mod", slides=slides)
    out = Path(tmp_path) / "renders" / carousel.carousel_id
    render_carousel(carousel, out_dir=out)
    cid = save_carousel(carousel, module_id=1, output_dir=str(out))
    # shelves should contain this carousel
    r = client.get("/api/v1/shelves", headers={"X-User-Id": uid})
    assert r.status_code == 200
    shelves = r.json()
    assert any(s["carousel_id"] == cid for s in shelves)
    # deck should have 2 cards unfiled
    r2 = client.get(f"/api/v1/deck?shelf={cid}", headers={"X-User-Id": uid})
    assert r2.status_code == 200
    deck = r2.json()
    assert deck["shelf_id"] == str(cid)
    assert len(deck["cards"]) == 2
    assert deck["cards"][0]["front"]["header"] == "Front A"
    assert deck["cards"][0]["back"]["back_header"] == "Back A"
    # file first card as mastered
    r3 = client.post("/api/v1/file", json={"post_id": str(cid), "slide_index": 0, "status": "mastered"}, headers={"X-User-Id": uid})
    assert r3.status_code == 200
    assert r3.json()["status"] == "mastered"
    assert r3.json()["shelf_fill"] == 0.5
    # shelf fill should be 0.5 now
    r4 = client.get("/api/v1/shelves", headers={"X-User-Id": uid})
    shelf = next(s for s in r4.json() if s["carousel_id"] == cid)
    assert shelf["fill_pct"] == 0.5
    assert shelf["mastered_count"] == 1
    # deck should now have 1 card (the other unfiled) — mastered not resurfaced
    r5 = client.get(f"/api/v1/deck?shelf={cid}", headers={"X-User-Id": uid})
    assert len(r5.json()["cards"]) == 1
    assert r5.json()["cards"][0]["slide_index"] == 1
    # file second as review
    client.post("/api/v1/file", json={"post_id": str(cid), "slide_index": 1, "status": "review"}, headers={"X-User-Id": uid})
    # deck should resurface review after unfiled exhausted: we have 0 unfiled, 1 review -> deck should show review card
    r6 = client.get(f"/api/v1/deck?shelf={cid}", headers={"X-User-Id": uid})
    assert len(r6.json()["cards"]) == 1
    assert r6.json()["cards"][0]["status"] == "review"
    # cabinet should have both
    rc = client.get("/api/v1/cabinet?tray=mastered", headers={"X-User-Id": uid})
    assert rc.json()["count"] == 1
    rc2 = client.get("/api/v1/cabinet?tray=review", headers={"X-User-Id": uid})
    assert rc2.json()["count"] == 1
