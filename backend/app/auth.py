"""Bearer-token authentication dependencies for the StudyReel API."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Header, HTTPException

from app.db.database import delete_session, get_session, get_user_by_id

SESSION_TTL_DAYS = int(os.getenv("SESSION_TTL_DAYS", "30"))


def _unauthorized(detail: str = "Invalid or expired token") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise _unauthorized("Missing bearer token")
    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Invalid authorization header")
    return token


def current_user(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> dict:
    """Resolve the Authorization bearer token to the owning user row."""
    token = _bearer_token(authorization)
    session = get_session(token)
    if not session:
        raise _unauthorized()

    created_at = session.get("created_at")
    if created_at:
        try:
            created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - created > timedelta(days=SESSION_TTL_DAYS):
                delete_session(token)
                raise _unauthorized("Session expired")
        except ValueError:
            pass

    user = get_user_by_id(session["user_id"])
    if not user:
        raise _unauthorized()
    return user


def require_admin_key(
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> None:
    """Operator-only routes: require the shared key from ADMIN_API_KEY."""
    expected = os.getenv("ADMIN_API_KEY", "").strip()
    supplied = (x_admin_key or "").strip()
    if not expected or not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="Valid X-Admin-Key header required")
