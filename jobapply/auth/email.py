"""Email delivery for verification and password-reset links.

Priority order:
  1. Resend API  — set RESEND_API_KEY (free 3,000/month, no SMTP setup)
  2. SMTP        — set SMTP_HOST + credentials
  3. Stdout      — dev/CI fallback when neither is configured

Get a free Resend key at https://resend.com (takes 2 minutes, no credit card).

Environment variables
----------------------
RESEND_API_KEY     Resend API key (re_...)          → uses Resend HTTP API
SMTP_HOST          SMTP server hostname              → uses SMTP
SMTP_PORT          SMTP port (default 465)
SMTP_USER          SMTP username (optional)
SMTP_PASSWORD      SMTP password (optional)
SMTP_TLS           'true' = SSL/TLS, 'false' = STARTTLS (default true)
EMAIL_FROM         Sender address (default noreply@jobapply.local)
APP_BASE_URL       Base URL for links (default http://localhost:8000)
"""

from __future__ import annotations

import os
import smtplib
import ssl
import urllib.request
import urllib.error
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ---------------------------------------------------------------------------
# Config — read once at import time
# ---------------------------------------------------------------------------

_RESEND_KEY   = os.environ.get("RESEND_API_KEY", "")
_SMTP_HOST    = os.environ.get("SMTP_HOST", "")
_SMTP_PORT    = int(os.environ.get("SMTP_PORT", "465"))
_SMTP_USER    = os.environ.get("SMTP_USER", "")
_SMTP_PASSWORD= os.environ.get("SMTP_PASSWORD", "")
_SMTP_TLS     = os.environ.get("SMTP_TLS", "true").lower() == "true"
_EMAIL_FROM   = os.environ.get("EMAIL_FROM", "onboarding@resend.dev")
_APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8000").rstrip("/")


# ---------------------------------------------------------------------------
# Resend HTTP API
# ---------------------------------------------------------------------------

def _send_via_resend(to: str, subject: str, body_html: str, body_text: str) -> None:
    payload = json.dumps({
        "from": _EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "html": body_html,
        "text": body_text,
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {_RESEND_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            _ = resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"Resend API error {exc.code}: {body}") from exc


# ---------------------------------------------------------------------------
# SMTP
# ---------------------------------------------------------------------------

def _send_via_smtp(to: str, subject: str, body_text: str, body_html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = _EMAIL_FROM
    msg["To"] = to
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))
    if _SMTP_TLS:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT, context=ctx) as server:
            if _SMTP_USER:
                server.login(_SMTP_USER, _SMTP_PASSWORD)
            server.sendmail(_EMAIL_FROM, to, msg.as_string())
    else:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            if _SMTP_USER:
                server.login(_SMTP_USER, _SMTP_PASSWORD)
            server.sendmail(_EMAIL_FROM, to, msg.as_string())


# ---------------------------------------------------------------------------
# Unified send
# ---------------------------------------------------------------------------

def _send(to: str, subject: str, body_text: str, body_html: str) -> None:
    if _RESEND_KEY:
        _send_via_resend(to, subject, body_html, body_text)
        return
    if _SMTP_HOST:
        _send_via_smtp(to, subject, body_text, body_html)
        return
    # Dev / CI fallback — print to terminal
    print(
        f"\n{'='*60}\n"
        f"[EMAIL — no provider configured]\n"
        f"  To get real emails: add RESEND_API_KEY to .env\n"
        f"  Get a free key at: https://resend.com\n"
        f"{'─'*60}\n"
        f"To:      {to}\n"
        f"Subject: {subject}\n"
        f"{'─'*60}\n"
        f"{body_text}\n"
        f"{'='*60}\n"
    )


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def send_verification_email(to: str, raw_token: str) -> None:
    link = f"{_APP_BASE_URL}/verify-email?token={raw_token}"
    subject = "Verify your JobApply account"
    body_text = (
        f"Hi,\n\n"
        f"Verify your email by clicking the link below.\n"
        f"Expires in 24 hours, single use.\n\n"
        f"{link}\n\n"
        f"If you didn't create a JobApply account, ignore this.\n"
    )
    body_html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px">
      <h2 style="color:#10b981;margin-bottom:8px">Verify your email</h2>
      <p style="color:#374151">Click the button below to activate your JobApply account.</p>
      <a href="{link}" style="display:inline-block;margin:20px 0;padding:12px 24px;
         background:#059669;color:#fff;text-decoration:none;border-radius:6px;font-weight:600">
        Verify email address
      </a>
      <p style="color:#6b7280;font-size:13px">Link expires in 24 hours and can only be used once.</p>
      <p style="color:#9ca3af;font-size:12px">If you didn't create this account, ignore this email.</p>
    </div>"""
    _send(to, subject, body_text, body_html)


def send_password_reset_email(to: str, raw_token: str) -> None:
    link = f"{_APP_BASE_URL}/reset-password?token={raw_token}"
    subject = "Reset your JobApply password"
    body_text = (
        f"Hi,\n\n"
        f"Click the link below to set a new password.\n"
        f"Expires in 1 hour, single use.\n\n"
        f"{link}\n\n"
        f"If you didn't request this, ignore this email.\n"
    )
    body_html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px">
      <h2 style="color:#10b981;margin-bottom:8px">Reset your password</h2>
      <p style="color:#374151">Click the button below to set a new password for your JobApply account.</p>
      <a href="{link}" style="display:inline-block;margin:20px 0;padding:12px 24px;
         background:#059669;color:#fff;text-decoration:none;border-radius:6px;font-weight:600">
        Reset password
      </a>
      <p style="color:#6b7280;font-size:13px">Link expires in 1 hour and can only be used once.</p>
      <p style="color:#9ca3af;font-size:12px">If you didn't request this, ignore this email.</p>
    </div>"""
    _send(to, subject, body_text, body_html)
