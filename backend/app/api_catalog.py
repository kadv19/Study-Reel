"""Card Catalog API: shelves, deck, filing, cabinet (PDF §4)."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from app.db.database import get_carousel, get_library_summary, get_shelf_summary, list_card_states, upsert_card_state
from app.schemas import FileCardRequest

router = APIRouter(prefix="/api/v1", tags=["catalog"])


def _uid(x_user_id: Optional[str] = Query(None), x_user_id_h: Optional[str] = Header(None, alias="X-User-Id")) -> str:
    return (x_user_id_h or x_user_id or "anon").strip() or "anon"


@router.get("/shelves")
def get_shelves(
    user_id: str = Header(None, alias="X-User-Id"),
    user_id_q: Optional[str] = Query(None, alias="user_id"),
    syllabus_id: Optional[str] = Query(None, description="filter to one book/syllabus"),
) -> list[dict]:
    uid = (user_id or user_id_q or "anon").strip() or "anon"
    shelves = get_shelf_summary(uid)
    if syllabus_id is not None:
        try:
            sid = int(syllabus_id)
            shelves = [s for s in shelves if s.get("syllabus_id") == sid]
        except:
            # allow string book_id filtering
            shelves = [s for s in shelves if str(s.get("syllabus_id")) == str(syllabus_id) or str(s.get("book_label")) == str(syllabus_id)]
    return shelves


@router.get("/books")
def get_books(
    user_id: str = Header(None, alias="X-User-Id"),
    user_id_q: Optional[str] = Query(None, alias="user_id"),
) -> list[dict]:
    uid = (user_id or user_id_q or "anon").strip() or "anon"
    return get_library_summary(uid)


@router.get("/library")
def get_library(
    user_id: str = Header(None, alias="X-User-Id"),
    user_id_q: Optional[str] = Query(None, alias="user_id"),
) -> list[dict]:
    uid = (user_id or user_id_q or "anon").strip() or "anon"
    return get_library_summary(uid)


@router.get("/deck")
def get_deck(
    shelf: str = Query(..., description="shelf_id (carousel id) or label"),
    user_id: str = Header(None, alias="X-User-Id"),
    user_id_q: Optional[str] = Query(None, alias="user_id"),
    replay: bool = Query(False, description="if true, return all cards ignoring filed status"),
    all: bool = Query(False, alias="all", description="alias for replay"),
) -> dict:
    uid = (user_id or user_id_q or "anon").strip() or "anon"
    do_replay = replay or all
    shelves = get_shelf_summary(uid)
    # find shelf by shelf_id or label
    target = None
    for s in shelves:
        if s["shelf_id"] == shelf or s["label"] == shelf or s["module_name"] == shelf:
            target = s
            break
    if not target:
        # try direct carousel id numeric — still enforce ownership
        try:
            cid = int(shelf)
            rec = get_carousel(cid)
            if rec:
                from app.db.database import _connect
                owned = False
                with _connect() as conn:
                    prow = conn.execute(
                        "SELECT s.owner_user_id FROM carousels c JOIN modules m ON m.id=c.module_id JOIN syllabi s ON s.id=m.syllabus_id WHERE c.id=?",
                        (cid,),
                    ).fetchone()
                    if prow and prow["owner_user_id"] == uid:
                        owned = True
                if owned:
                    data = rec["carousel"]
                    target = {"shelf_id": str(cid), "label": data.get("module_name","")[:12], "module_name": data.get("module_name",""), "carousel_id": cid, "total_slides": len(data.get("slides",[])), "mastered_count": 0, "fill_pct": 0}
        except Exception:
            pass
    if not target or target.get("carousel_id") is None:
        raise HTTPException(404, f"Shelf {shelf} not found — upload syllabus and render first")
    cid = target["carousel_id"]
    rec = get_carousel(cid)
    if not rec:
        raise HTTPException(404, f"Carousel {cid} not found")
    carousel = rec["carousel"]
    slides = carousel.get("slides", [])
    states = list_card_states(uid)
    status_map = {r["card_key"]: r["status"] for r in states}
    if do_replay:
        # Replay: ignore filed status, show all cards in order
        deck_cards = []
        for idx, sl in enumerate(slides):
            key = f"{cid}:{idx}"
            st = status_map.get(key, "unfiled")
            topic = sl.get("topic", {})
            card = {
                "card_key": key,
                "post_id": str(cid),
                "slide_index": idx,
                "status": st,
                "front": {
                    "header": topic.get("header",""),
                    "body": topic.get("body",""),
                    "code": topic.get("code_block"),
                    "language": topic.get("language_tag") or "python",
                    "slide_number": idx+1,
                    "total_slides": len(slides),
                    "diagram": topic.get("diagram"),
                },
                "back": {
                    "back_header": topic.get("back_header") or "Why it matters",
                    "back_body": topic.get("back_body") or "Exam focus: practice this concept with a diagram or formula.",
                    "exam_weight": topic.get("exam_weight") or "medium",
                },
                "exam_weight": topic.get("exam_weight") or "medium",
            }
            deck_cards.append(card)
    else:
        # Normal: unfiled first, then review
        unfiled = []
        review = []
        for idx, sl in enumerate(slides):
            key = f"{cid}:{idx}"
            st = status_map.get(key, "unfiled")
            topic = sl.get("topic", {})
            card = {
                "card_key": key,
                "post_id": str(cid),
                "slide_index": idx,
                "status": st,
                "front": {
                    "header": topic.get("header",""),
                    "body": topic.get("body",""),
                    "code": topic.get("code_block"),
                    "language": topic.get("language_tag") or "python",
                    "slide_number": idx+1,
                    "total_slides": len(slides),
                    "diagram": topic.get("diagram"),
                },
                "back": {
                    "back_header": topic.get("back_header") or "Why it matters",
                    "back_body": topic.get("back_body") or "Exam focus: practice this concept with a diagram or formula.",
                    "exam_weight": topic.get("exam_weight") or "medium",
                },
                "exam_weight": topic.get("exam_weight") or "medium",
            }
            if st == "unfiled":
                unfiled.append(card)
            elif st == "review":
                review.append(card)
            elif st in ("catalog","mastered"):
                continue
        deck_cards = unfiled + review
    return {
        "shelf_id": target["shelf_id"],
        "shelf_label": target["label"],
        "module_name": target["module_name"],
        "total_slides": target["total_slides"],
        "fill_pct": target["fill_pct"],
        "cards": deck_cards,
    }


@router.post("/file")
def file_card(
    payload: FileCardRequest,
    user_id: str = Header(None, alias="X-User-Id"),
    user_id_q: Optional[str] = Query(None, alias="user_id"),
) -> dict:
    uid = (user_id or user_id_q or "anon").strip() or "anon"
    # validate carousel exists
    try:
        cid = int(payload.post_id)
    except:
        cid = payload.post_id
        try:
            cid = int(cid)
        except:
            raise HTTPException(400, "post_id must be carousel id")
    rec = get_carousel(cid)
    if not rec:
        raise HTTPException(404, f"Carousel {cid} not found")
    total = len(rec["carousel"].get("slides", []))
    if payload.slide_index >= total:
        raise HTTPException(400, f"slide_index {payload.slide_index} out of range 0..{total-1}")
    row = upsert_card_state(uid, cid, payload.slide_index, payload.status)
    # recalc fill
    shelves = get_shelf_summary(uid)
    fill = next((s["fill_pct"] for s in shelves if str(s["carousel_id"]) == str(cid)), 0)
    return {"card_key": f"{cid}:{payload.slide_index}", "status": payload.status, "shelf_fill": fill, "row": row}


@router.get("/cabinet")
def get_cabinet(
    tray: str = Query(..., description="review|catalog|mastered"),
    user_id: str = Header(None, alias="X-User-Id"),
    user_id_q: Optional[str] = Query(None, alias="user_id"),
) -> dict:
    uid = (user_id or user_id_q or "anon").strip() or "anon"
    if tray not in ("review","catalog","mastered"):
        raise HTTPException(400, "tray must be review|catalog|mastered")
    states = list_card_states(uid, status=tray)
    cards = []
    for r in states:
        cid = r["carousel_id"]
        idx = r["slide_index"]
        rec = get_carousel(cid)
        title = f"Card {cid}:{idx}"
        header = title
        tag = "Unknown"
        if rec:
            try:
                sl = rec["carousel"]["slides"][idx]
                header = sl["topic"]["header"]
                tag = rec["carousel"].get("module_name","")[:12] or f"Mod {cid}"
            except:
                pass
        cards.append({
            "card_key": r["card_key"],
            "post_id": str(cid),
            "slide_index": idx,
            "title": header,
            "tag": tag,
            "status": tray,
            "filed_at": r.get("filed_at"),
        })
    return {"tray": tray, "count": len(cards), "cards": cards}
