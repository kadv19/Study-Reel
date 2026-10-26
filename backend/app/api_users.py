"""Real authentication — bcrypt, opaque session tokens, NIE email verification."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import NoReturn

import bcrypt
from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user
from app.db.database import (
    create_session,
    create_user_with_password,
    get_user_by_email,
    get_user_by_id,
    increment_user_verification_attempts,
    list_colleges,
    mark_user_email_verified,
    migrate_anon_cards,
    set_user_verification_code,
    upsert_user,
)
from app.emailer import send_verification_email
from app.schemas import (
    COLLEGE_LABELS,
    AuthResponse,
    LoginRequest,
    ResendRequest,
    SignupRequest,
    UserCreate,
    UserOut,
    VerifyRequest,
)

router = APIRouter(prefix="/api/v1", tags=["users"])

VERIFY_CODE_TTL = timedelta(minutes=10)
VERIFY_MAX_ATTEMPTS = 5
VERIFY_RESEND_SECONDS = 60
NIE_DOMAIN = "nie.ac.in"
NIE_ONLY_DETAIL = "Only NIE student emails (@nie.ac.in) are allowed."


def _hash_password(password: str) -> str:
    pw = password.encode("utf-8")
    hashed = bcrypt.hashpw(pw, bcrypt.gensalt())
    return hashed.decode("utf-8")


def _verify_password(password: str, hash_str: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hash_str.encode("utf-8"))
    except Exception:
        return False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _allowed_domains() -> set[str]:
    raw = os.getenv("ALLOWED_EMAIL_DOMAINS", NIE_DOMAIN)
    return {
        domain.strip().lower().lstrip("@")
        for domain in raw.split(",")
        if domain.strip()
    }


def _email_domain(email: str) -> str:
    return email.strip().lower().rsplit("@", 1)[-1]


def _is_allowed_email(email: str) -> bool:
    return _email_domain(email) in _allowed_domains()


def _college_for_email(email: str) -> str:
    return "NIE"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def _issue_verification_code(email: str) -> str:
    code = _generate_code()
    now = _utcnow()
    set_user_verification_code(
        email,
        _hash_code(code),
        now + VERIFY_CODE_TTL,
        sent_at=now,
    )
    await send_verification_email(email, code)
    return code


def _raise_email_unverified() -> NoReturn:
    raise HTTPException(status_code=403, detail="EMAIL_UNVERIFIED")


@router.post("/auth/signup", response_model=AuthResponse)
async def signup(payload: SignupRequest) -> AuthResponse:
    email = payload.email.strip().lower()
    if not _is_allowed_email(email):
        raise HTTPException(status_code=400, detail=NIE_ONLY_DETAIL)
    existing = get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    pw_hash = _hash_password(payload.password)
    create_user_with_password(
        payload.name,
        email,
        _college_for_email(email),
        pw_hash,
    )
    await _issue_verification_code(email)
    _raise_email_unverified()


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
    if not user.get("email_verified"):
        _raise_email_unverified()
    token = create_session(user["id"])
    return AuthResponse(token=token, user_id=user["id"], user=UserOut(**user))


@router.post("/auth/verify")
def verify_email(payload: VerifyRequest) -> dict:
    user = get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
    if not _is_allowed_email(user["email"]):
        raise HTTPException(status_code=400, detail=NIE_ONLY_DETAIL)
    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Email already verified")

    code_hash = user.get("verify_code_hash")
    if not code_hash:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    attempts = int(user.get("verify_attempts") or 0)
    if attempts >= VERIFY_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many incorrect attempts. Request a new code.",
        )

    expires = user.get("verify_expires")
    if expires is not None and _as_utc(expires) < _utcnow():
        raise HTTPException(
            status_code=400,
            detail="Verification code expired. Request a new code.",
        )

    if not hmac.compare_digest(_hash_code(payload.code), code_hash):
        attempts = increment_user_verification_attempts(user["id"])
        if attempts >= VERIFY_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail="Too many incorrect attempts. Request a new code.",
            )
        raise HTTPException(status_code=400, detail="Invalid verification code")

    mark_user_email_verified(user["id"])
    return {"ok": True, "email_verified": True}


@router.post("/auth/resend")
async def resend_verification(payload: ResendRequest) -> dict:
    user = get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not _is_allowed_email(user["email"]):
        raise HTTPException(status_code=400, detail=NIE_ONLY_DETAIL)
    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Email already verified")

    sent_at = user.get("verify_sent_at")
    if sent_at is not None:
        elapsed = (_utcnow() - _as_utc(sent_at)).total_seconds()
        if elapsed < VERIFY_RESEND_SECONDS:
            retry_after = max(1, int(VERIFY_RESEND_SECONDS - elapsed) + 1)
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {retry_after} seconds before requesting another code.",
                headers={"Retry-After": str(retry_after)},
            )

    await _issue_verification_code(user["email"])
    return {
        "ok": True,
        "message": "Verification code sent",
        "retry_after": VERIFY_RESEND_SECONDS,
    }


@router.post("/auth/logout")
def logout(payload: dict) -> dict:
    token = payload.get("token") or payload.get("session_token")
    if not token:
        raise HTTPException(status_code=400, detail="token required")
    from app.db.database import delete_session

    delete_session(token)
    return {"ok": True}


@router.get("/auth/me", response_model=UserOut)
def me(user: dict = Depends(current_user)) -> UserOut:
    return UserOut(**user)


@router.get("/colleges")
def get_colleges() -> list[dict]:
    cols = list_colleges()
    if cols:
        return cols
    # fallback from schema constants
    return [{"code": k, "label": v} for k, v in COLLEGE_LABELS.items()]


@router.post("/users", response_model=UserOut)
def create_user(payload: UserCreate, user: dict = Depends(current_user)) -> UserOut:
    try:
        row = upsert_user(payload.name, payload.email, payload.college)
        return UserOut(**row)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: str, user: dict = Depends(current_user)) -> UserOut:
    if user_id != user["id"]:
        raise HTTPException(403, "You can only read your own profile")
    row = get_user_by_id(user_id)
    if not row:
        raise HTTPException(404, "User not found")
    return UserOut(**row)


@router.post("/users/migrate")
def migrate(payload: dict, user: dict = Depends(current_user)) -> dict:
    old_id = payload.get("from_id") or payload.get("old_id") or payload.get("from")
    new_id = payload.get("to_id") or payload.get("new_id") or payload.get("to")
    if not old_id or not new_id:
        raise HTTPException(400, "from_id and to_id required")
    if new_id != user["id"]:
        raise HTTPException(403, "You can only migrate cards into your own account")
    # verify new user exists
    if not get_user_by_id(new_id):
        raise HTTPException(404, "new user not found")
    moved = migrate_anon_cards(old_id, new_id)
    return {"migrated": moved, "from": old_id, "to": new_id}
