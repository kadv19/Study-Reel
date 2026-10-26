"""NIE-only signup and email verification tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app.api_users as api_users
from app.db.database import get_user_by_email
from app.main import app

NIE_ONLY_DETAIL = "Only NIE student emails (@nie.ac.in) are allowed."
PASSWORD = "secret123"


@pytest.fixture
def client_ctx():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sent_codes(monkeypatch):
    codes: list[tuple[str, str]] = []

    async def fake_send(to_email: str, code: str) -> None:
        codes.append((to_email, code))

    monkeypatch.setattr(api_users, "send_verification_email", fake_send)
    return codes


def _nie_email() -> str:
    return f"student-{uuid.uuid4().hex[:12]}@nie.ac.in"


def _signup(client: TestClient, email: str, college: str = "VVCE"):
    return client.post(
        "/api/v1/auth/signup",
        json={
            "name": "NIE Student",
            "email": email,
            "college": college,
            "password": PASSWORD,
        },
    )


def _login(client: TestClient, email: str):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )


def _verify(client: TestClient, email: str, code: str):
    return client.post(
        "/api/v1/auth/verify",
        json={"email": email, "code": code},
    )


def _wrong_code(code: str) -> str:
    return "000000" if code != "000000" else "111111"


def test_signup_rejects_short_password(client_ctx, sent_codes):
    response = client_ctx.post(
        "/api/v1/auth/signup",
        json={
            "name": "NIE Student",
            "email": _nie_email(),
            "password": "short7x",
        },
    )
    assert response.status_code == 422
    assert sent_codes == []


def test_signup_rejects_non_nie_domains(client_ctx):
    for email in (
        "student@example.com",
        "student@vvce.ac.in",
        "student@nie.ac.in.evil.com",
    ):
        response = _signup(client_ctx, email)
        assert response.status_code == 400
        assert response.json()["detail"] == NIE_ONLY_DETAIL


def test_signup_requires_verification_then_login_succeeds(client_ctx, sent_codes):
    email = _nie_email()
    response = _signup(client_ctx, email, college="VVCE")

    assert response.status_code == 403
    assert response.json()["detail"] == "EMAIL_UNVERIFIED"
    assert len(sent_codes) == 1
    sent_to, code = sent_codes[0]
    assert sent_to == email
    assert len(code) == 6 and code.isdigit()

    user = get_user_by_email(email)
    assert user is not None
    assert user["college"] == "NIE"
    assert user["email_verified"] is False
    assert user["verify_code_hash"] != code

    response = _login(client_ctx, email)
    assert response.status_code == 403
    assert response.json()["detail"] == "EMAIL_UNVERIFIED"

    response = _verify(client_ctx, email, _wrong_code(code))
    assert response.status_code == 400

    response = _verify(client_ctx, email, code)
    assert response.status_code == 200
    assert response.json()["email_verified"] is True

    user = get_user_by_email(email)
    assert user["email_verified"] is True
    assert user["verify_code_hash"] is None
    assert user["verify_expires"] is None

    response = _login(client_ctx, email)
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"]["email"] == email


def test_expired_verification_code_is_rejected(
    client_ctx, sent_codes, monkeypatch
):
    email = _nie_email()
    assert _signup(client_ctx, email).status_code == 403
    code = sent_codes[0][1]

    future = datetime.now(timezone.utc) + timedelta(minutes=11)
    monkeypatch.setattr(api_users, "_utcnow", lambda: future)

    response = _verify(client_ctx, email, code)
    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()


def test_verification_locks_out_after_five_wrong_attempts(
    client_ctx, sent_codes
):
    email = _nie_email()
    assert _signup(client_ctx, email).status_code == 403
    code = sent_codes[0][1]
    wrong = _wrong_code(code)

    for _ in range(4):
        response = _verify(client_ctx, email, wrong)
        assert response.status_code == 400

    response = _verify(client_ctx, email, wrong)
    assert response.status_code == 429

    # Even the correct code is rejected until a new code is requested.
    response = _verify(client_ctx, email, code)
    assert response.status_code == 429


def test_resend_enforces_cooldown_and_issues_new_code(
    client_ctx, sent_codes, monkeypatch
):
    email = _nie_email()
    assert _signup(client_ctx, email).status_code == 403
    first_code = sent_codes[0][1]

    response = client_ctx.post("/api/v1/auth/resend", json={"email": email})
    assert response.status_code == 429
    assert "Retry-After" in response.headers

    future = datetime.now(timezone.utc) + timedelta(seconds=61)
    monkeypatch.setattr(api_users, "_utcnow", lambda: future)

    response = client_ctx.post("/api/v1/auth/resend", json={"email": email})
    assert response.status_code == 200
    assert response.json()["retry_after"] == 60
    assert len(sent_codes) == 2
    second_code = sent_codes[1][1]

    response = client_ctx.post("/api/v1/auth/resend", json={"email": email})
    assert response.status_code == 429

    response = _verify(client_ctx, email, second_code)
    assert response.status_code == 200

    assert first_code.isdigit() and second_code.isdigit()
