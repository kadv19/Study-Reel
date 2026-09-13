"""Real authentication — bcrypt + opaque session tokens (NIE/VVCE/SJCE)."""

from __future__ import annotations

import bcrypt

from fastapi import APIRouter, HTTPException

from app.db.database import (
    create_session,
    create_user_with_password,
    get_session,
    get_user_by_email,
    get_user_by_id,
    get_user_by_token,
    list_colleges,
    migrate_anon_cards,
    upsert_user,
)
from app.schemas import COLLEGE_LABELS, AuthResponse, LoginRequest, SignupRequest, UserCreate, UserOut

router = APIRouter(prefix="/api/v1", tags=["users"])


def _hash_password(password: str) -> str:
    pw = password.encode("utf-8")
    hashed = bcrypt.hashpw(pw, bcrypt.gensalt())
    return hashed.decode("utf-8")


def _verify_password(password: str, hash_str: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hash_str.encode("utf-8"))
    except Exception:
        return False


@router.post("/auth/signup", response_model=AuthResponse)
def signup(payload: SignupRequest) -> AuthResponse:
    # check existing
    existing = get_user_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    pw_hash = _hash_password(payload.password)
    row = create_user_with_password(payload.name, payload.email, payload.college, pw_hash)
    token = create_session(row["id"])
    return AuthResponse(token=token, user_id=row["id"], user=UserOut(**row))


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    user = get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    stored = user.get("password_hash")
    if not stored:
        # user created via old pseudo flow has no password — force signup again
        raise HTTPException(status_code=401, detail="No password set for this account — please sign up again")
    if not _verify_password(payload.password, stored):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_session(user["id"])
    return AuthResponse(token=token, user_id=user["id"], user=UserOut(**user))


@router.post("/auth/logout")
def logout(payload: dict) -> dict:
    token = payload.get("token") or payload.get("session_token")
    if not token:
        raise HTTPException(status_code=400, detail="token required")
    from app.db.database import delete_session

    delete_session(token)
    return {"ok": True}


@router.get("/auth/me", response_model=UserOut)
def me(token: str | None = None) -> UserOut:
    # simple token check via query param for debugging
    if not token:
        raise HTTPException(status_code=401, detail="token required")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return UserOut(**user)


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
