"""Verification email delivery via Brevo SMTP (async)."""

from __future__ import annotations

import os
from email.message import EmailMessage

import aiosmtplib


async def _send_code_email(
    to_email: str, subject: str, intro: str, code: str, label: str
) -> None:
    if os.getenv("ENV", "dev").strip().lower() == "dev":
        print(f"[dev] {label} code for {to_email}: {code}", flush=True)
        return

    host = os.getenv("SMTP_HOST", "smtp-relay.brevo.com").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASS", "")
    sender = os.getenv("SMTP_FROM", "").strip() or username

    if not username or not password or not sender:
        raise RuntimeError("SMTP_USER, SMTP_PASS, and SMTP_FROM must be configured")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(
        f"{intro}\n\n"
        f"Your StudyReel {label.lower()} code is {code}.\n\n"
        "It expires in 10 minutes. If you did not request this, you can ignore this email."
    )

    await aiosmtplib.send(
        message,
        hostname=host,
        port=port,
        username=username,
        password=password,
        start_tls=port not in (465,),
        use_tls=port == 465,
        timeout=20,
    )


async def send_verification_email(to_email: str, code: str) -> None:
    """Send a 6-digit verification code, or print it when ENV=dev."""
    await _send_code_email(
        to_email,
        "Your StudyReel verification code",
        "Verify your StudyReel account with this code.",
        code,
        "Verification",
    )


async def send_password_reset_email(to_email: str, code: str) -> None:
    """Send a 6-digit password reset code, or print it when ENV=dev."""
    await _send_code_email(
        to_email,
        "Reset your StudyReel password",
        "Someone asked to reset the password for this StudyReel account. "
        "If that was you, use this code to choose a new password.",
        code,
        "Password reset",
    )
