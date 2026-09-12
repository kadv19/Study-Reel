"""Pseudonymous accounts — C (no password, UUID, dropdown college)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db.database import get_user_by_id, list_colleges, migrate_anon_cards, upsert_user
from app.schemas import COLLEGE_LABELS, UserCreate, UserOut

router = APIRouter(prefix="/api/v1", tags=["users"])


@router.get("/colleges")
def get_colleges() -> list[dict]:
    cols = list_colleges()
    if cols:
        return cols
    # fallback from schema constants
    return [{"code": k, "label": v} for k, v in COLLEGE_LABELS.items()]


@router.post("/users", response_model=UserOut)
def create_user(payload: UserCreate) -> UserOut:
    try:
        row = upsert_user(payload.name, payload.email, payload.college)
        return UserOut(**row)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: str) -> UserOut:
    row = get_user_by_id(user_id)
    if not row:
        raise HTTPException(404, "User not found")
    return UserOut(**row)


@router.post("/users/migrate")
def migrate(payload: dict) -> dict:
    old_id = payload.get("from_id") or payload.get("old_id") or payload.get("from")
    new_id = payload.get("to_id") or payload.get("new_id") or payload.get("to")
    if not old_id or not new_id:
        raise HTTPException(400, "from_id and to_id required")
    # verify new user exists
    if not get_user_by_id(new_id):
        raise HTTPException(404, "new user not found")
    moved = migrate_anon_cards(old_id, new_id)
    return {"migrated": moved, "from": old_id, "to": new_id}
