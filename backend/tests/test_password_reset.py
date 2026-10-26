"""Forgot-password and reset-password flow tests."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import app.api_users as api_users
from app.main import app

NIE_ONLY_DETAIL = "Only NIE student emails (@nie.ac.in) are allowed."
PASSWORD = "secret123"
NEW_PASSWORD = "brandnew456"


@pytest.fixture
def client_ctx():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sent_resets(monkeypatch):
    resets: list[tuple[str, str]] = []

    async def fake_send(to_email: str, code: str) -> None:
        resets.append((to_email, code))

    async def fake_verify(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(api_users, "send_password_reset_email", fake_send)
    monkeypatch.setattr(api_users, "send_verification_email", fake_verify)
    return resets


def _nie_email() -> str:
    return f"student-{uuid.uuid4().hex[:12]}@nie.ac.in"


def _signup(client: TestClient, email: str):
    return client.post(
        "/api/v1/auth/signup",
        json={
            "name": "NIE Student",
            "email": email,
            "password": PASSWORD,
        },
    )


def _login(client: TestClient, email: str, password: str = PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


def test_forgot_password_sends_code_and_reset_works(client_ctx, sent_resets):
    email = _nie_email()
    assert _signup(client_ctx, email).status_code == 403

    response = client_ctx.post("/api/v1/auth/forgot-password", json={"email": email})
    assert response.status_code == 200
    assert response.json()["ok"] is True

    assert len(sent_resets) == 1
    sent_to, code = sent_resets[0]
    assert sent_to == email
    assert len(code) == 6 and code.isdigit()

    wrong = "000000" if code != "000000" else "111111"
    response = client_ctx.post(
        "/api/v1/auth/reset-password",
        json={"email": email, "code": wrong, "password": NEW_PASSWORD},
    )
    assert response.status_code == 400

    response = client_ctx.post(
        "/api/v1/auth/reset-password",
        json={"email": email, "code": code, "password": NEW_PASSWORD},
    )
    assert response.status_code == 200

    assert _login(client_ctx, email, PASSWORD).status_code == 401
    response = _login(client_ctx, email, NEW_PASSWORD)
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"]["email"] == email


def test_forgot_password_unknown_email_stays_generic(client_ctx, sent_resets):
    email = _nie_email()
    response = client_ctx.post("/api/v1/auth/forgot-password", json={"email": email})
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert sent_resets == []

    response = client_ctx.post(
        "/api/v1/auth/reset-password",
        json={"email": email, "code": "123456", "password": NEW_PASSWORD},
    )
    assert response.status_code == 400


def test_forgot_password_rejects_non_nie_domain(client_ctx, sent_resets):
    response = client_ctx.post(
        "/api/v1/auth/forgot-password",
        json={"email": "student@example.com"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == NIE_ONLY_DETAIL
    assert sent_resets == []
