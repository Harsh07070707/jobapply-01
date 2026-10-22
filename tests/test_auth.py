"""Authentication integration tests.

Uses the shared fixtures from conftest.py:
  platform_client  — FastAPI TestClient with get_db overridden to the test DB
  platform_db      — per-test SQLAlchemy session for direct SQL assertions

Tests cover:
  - Registration (happy path, duplicate email, weak password, invalid email)
  - Password stored as bcrypt hash (never plaintext)
  - Email verification (real token via endpoint, bad token, expired, reuse)
  - Login (happy path, wrong password, unknown email, unverified → 403)
  - Same error message for wrong email vs wrong password (anti-enumeration)
  - /me endpoint (verified user, unverified user, no token, malformed token)
  - Token refresh (valid, revoked after logout, unknown token)
  - Logout (revokes refresh token)
  - Password reset (request always 202, confirm happy path, reuse rejected)
  - Expired access token rejected
  - Cross-user isolation:
      - Token for User A cannot impersonate User B
      - Forged user_id in token is rejected
      - Refresh token returns the correct user's identity
      - Fake reset token cannot change another user's password
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from jobapply.auth.tokens import (
    create_access_token,
    generate_opaque_token,
    hash_token,
    token_expiry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reg(client: TestClient, email: str, pw: str = "Password1!"):
    return client.post("/api/auth/register", json={"email": email, "password": pw})


def _email() -> str:
    return f"u_{uuid.uuid4().hex[:10]}@test.com"


def _verify_direct(db: Session, email: str) -> None:
    """Bypass the email link and mark the account verified directly in DB."""
    db.expire_all()  # see latest committed state from other connections
    now = datetime.now(timezone.utc)
    db.execute(
        text("UPDATE users SET email_verified_at = :now WHERE email = :e"),
        {"now": now, "e": email},
    )
    db.execute(
        text(
            "UPDATE email_tokens SET used_at = :now "
            "WHERE user_id = (SELECT user_id FROM users WHERE email = :e) "
            "AND purpose = 'email_verification' AND used_at IS NULL"
        ),
        {"now": now, "e": email},
    )
    db.commit()


def _reg_verify(client: TestClient, db: Session) -> str:
    """Register + verify; return email."""
    email = _email()
    assert _reg(client, email).status_code == 201
    _verify_direct(db, email)
    return email


def _login(client: TestClient, email: str, pw: str = "Password1!") -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _uid(db: Session, email: str) -> str:
    # Expire all cached objects so we see the latest committed data
    # from other connections (e.g. the TestClient's sessions).
    db.expire_all()
    row = db.execute(
        text("SELECT user_id FROM users WHERE email = :e"), {"e": email}
    ).fetchone()
    assert row, f"User not found: {email}"
    return str(row.user_id)


def _insert_token(db: Session, uid: str, purpose: str, expire_secs: int = 3600) -> str:
    """Insert a known raw token; return it."""
    raw = generate_opaque_token()
    db.execute(
        text(
            "INSERT INTO email_tokens "
            "(token_id, user_id, token_hash, purpose, expires_at, created_at) "
            "VALUES (:tid, :uid, :h, :p, :exp, :now)"
        ),
        {
            "tid": str(uuid.uuid4()),
            "uid": uid,
            "h": hash_token(raw),
            "p": purpose,
            "exp": token_expiry(expire_secs),
            "now": datetime.now(timezone.utc),
        },
    )
    db.commit()
    return raw


# ===========================================================================
# Registration
# ===========================================================================

class TestRegistration:
    def test_happy_path(self, platform_client, platform_db):
        r = _reg(platform_client, _email())
        assert r.status_code == 201
        body = r.json()
        assert "user_id" in body
        assert "message" in body

    def test_duplicate_email_is_409(self, platform_client, platform_db):
        email = _email()
        assert _reg(platform_client, email).status_code == 201
        assert _reg(platform_client, email).status_code == 409

    def test_weak_password_is_422(self, platform_client):
        assert _reg(platform_client, _email(), "short").status_code == 422

    def test_invalid_email_is_422(self, platform_client):
        assert _reg(platform_client, "not-an-email").status_code == 422

    def test_password_stored_as_bcrypt_hash(self, platform_client, platform_db):
        email = _email()
        _reg(platform_client, email, "MySecret99!")
        row = platform_db.execute(
            text("SELECT password_hash FROM users WHERE email = :e"), {"e": email}
        ).fetchone()
        assert row is not None
        assert row.password_hash != "MySecret99!"
        assert row.password_hash.startswith("$2b$")


# ===========================================================================
# Email verification
# ===========================================================================

class TestEmailVerification:
    def test_account_unverified_after_register(self, platform_client, platform_db):
        email = _email()
        _reg(platform_client, email)
        row = platform_db.execute(
            text("SELECT email_verified_at FROM users WHERE email = :e"), {"e": email}
        ).fetchone()
        assert row.email_verified_at is None

    def test_verify_endpoint_happy_path(self, platform_client, platform_db):
        email = _email()
        _reg(platform_client, email)
        raw = _insert_token(platform_db, _uid(platform_db, email), "email_verification")
        r = platform_client.get("/api/auth/verify-email", params={"token": raw})
        assert r.status_code == 200

    def test_verify_token_is_single_use(self, platform_client, platform_db):
        email = _email()
        _reg(platform_client, email)
        raw = _insert_token(platform_db, _uid(platform_db, email), "email_verification")
        platform_client.get("/api/auth/verify-email", params={"token": raw})
        r2 = platform_client.get("/api/auth/verify-email", params={"token": raw})
        assert r2.status_code == 400

    def test_bad_token_is_400(self, platform_client):
        r = platform_client.get("/api/auth/verify-email", params={"token": "garbage"})
        assert r.status_code == 400

    def test_expired_token_is_400(self, platform_client, platform_db):
        email = _email()
        _reg(platform_client, email)
        raw = _insert_token(platform_db, _uid(platform_db, email), "email_verification", expire_secs=-60)
        r = platform_client.get("/api/auth/verify-email", params={"token": raw})
        assert r.status_code == 400


# ===========================================================================
# Login
# ===========================================================================

class TestLogin:
    def test_happy_path_returns_tokens(self, platform_client, platform_db):
        email = _reg_verify(platform_client, platform_db)
        r = platform_client.post("/api/auth/login", json={"email": email, "password": "Password1!"})
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    def test_wrong_password_is_401(self, platform_client, platform_db):
        email = _reg_verify(platform_client, platform_db)
        r = platform_client.post("/api/auth/login", json={"email": email, "password": "Wrong99!"})
        assert r.status_code == 401

    def test_unknown_email_is_401(self, platform_client):
        r = platform_client.post("/api/auth/login", json={"email": "nobody@x.com", "password": "Pw1!"})
        assert r.status_code == 401

    def test_unverified_user_is_403(self, platform_client):
        email = _email()
        _reg(platform_client, email)
        r = platform_client.post("/api/auth/login", json={"email": email, "password": "Password1!"})
        assert r.status_code == 403

    def test_same_error_message_prevents_enumeration(self, platform_client, platform_db):
        email = _reg_verify(platform_client, platform_db)
        r1 = platform_client.post("/api/auth/login", json={"email": "no@x.com", "password": "Password1!"})
        r2 = platform_client.post("/api/auth/login", json={"email": email, "password": "WrongPw1!"})
        assert r1.json()["detail"] == r2.json()["detail"]


# ===========================================================================
# /me endpoint
# ===========================================================================

class TestMe:
    def test_no_token_returns_4xx(self, platform_client):
        r = platform_client.get("/api/auth/me")
        assert r.status_code in (401, 403)

    def test_malformed_token_is_401(self, platform_client):
        r = platform_client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
        assert r.status_code == 401

    def test_verified_user_returns_correct_profile(self, platform_client, platform_db):
        email = _reg_verify(platform_client, platform_db)
        tokens = _login(platform_client, email)
        r = platform_client.get("/api/auth/me", headers=_bearer(tokens["access_token"]))
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == email
        assert body["email_verified"] is True
        assert body["status"] == "active"

    def test_unverified_user_shows_unverified_flag(self, platform_client, platform_db):
        email = _email()
        _reg(platform_client, email)
        uid = _uid(platform_db, email)
        token = create_access_token(uid)
        r = platform_client.get("/api/auth/me", headers=_bearer(token))
        assert r.status_code == 200
        assert r.json()["email_verified"] is False


# ===========================================================================
# Refresh and logout
# ===========================================================================

class TestRefreshAndLogout:
    def test_refresh_happy_path(self, platform_client, platform_db):
        email = _reg_verify(platform_client, platform_db)
        tokens = _login(platform_client, email)
        r = platform_client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_logout_revokes_refresh_token(self, platform_client, platform_db):
        email = _reg_verify(platform_client, platform_db)
        tokens = _login(platform_client, email)
        platform_client.post("/api/auth/logout", json={"refresh_token": tokens["refresh_token"]})
        r = platform_client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert r.status_code == 401

    def test_logout_unknown_token_still_200(self, platform_client):
        r = platform_client.post("/api/auth/logout", json={"refresh_token": "not-real"})
        assert r.status_code == 200

    def test_invalid_refresh_token_is_401(self, platform_client):
        r = platform_client.post("/api/auth/refresh", json={"refresh_token": "garbage"})
        assert r.status_code == 401


# ===========================================================================
# Password reset
# ===========================================================================

class TestPasswordReset:
    def test_request_always_returns_202(self, platform_client):
        r1 = platform_client.post("/api/auth/password-reset/request", json={"email": "no@x.com"})
        r2 = platform_client.post("/api/auth/password-reset/request", json={"email": "also@no.com"})
        assert r1.status_code == 202
        assert r2.status_code == 202

    def test_confirm_happy_path(self, platform_client, platform_db):
        email = _reg_verify(platform_client, platform_db)
        uid = _uid(platform_db, email)
        raw = _insert_token(platform_db, uid, "password_reset")
        r = platform_client.post(
            "/api/auth/password-reset/confirm",
            json={"token": raw, "new_password": "NewPw9999!"},
        )
        assert r.status_code == 200
        # Can log in with new password
        r2 = platform_client.post("/api/auth/login", json={"email": email, "password": "NewPw9999!"})
        assert r2.status_code == 200

    def test_bad_token_is_400(self, platform_client):
        r = platform_client.post(
            "/api/auth/password-reset/confirm",
            json={"token": "garbage", "new_password": "NewPw9999!"},
        )
        assert r.status_code == 400

    def test_reuse_is_400(self, platform_client, platform_db):
        email = _reg_verify(platform_client, platform_db)
        uid = _uid(platform_db, email)
        raw = _insert_token(platform_db, uid, "password_reset")
        platform_client.post(
            "/api/auth/password-reset/confirm",
            json={"token": raw, "new_password": "NewPw9999!"},
        )
        r = platform_client.post(
            "/api/auth/password-reset/confirm",
            json={"token": raw, "new_password": "AnotherPw9!"},
        )
        assert r.status_code == 400


# ===========================================================================
# Token enforcement
# ===========================================================================

class TestTokenEnforcement:
    def test_expired_access_token_is_401(self, platform_client, platform_db):
        email = _reg_verify(platform_client, platform_db)
        uid = _uid(platform_db, email)
        from jose import jwt as jose_jwt
        payload = {
            "sub": uid,
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=16),
            "type": "access",
        }
        expired = jose_jwt.encode(payload, os.environ["SECRET_KEY"], algorithm="HS256")
        r = platform_client.get("/api/auth/me", headers=_bearer(expired))
        assert r.status_code == 401

    def test_wrong_token_type_is_401(self, platform_client):
        """A token with type='refresh' must not be accepted as an access token."""
        from jose import jwt as jose_jwt
        payload = {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "iat": datetime.now(timezone.utc),
            "type": "refresh",     # wrong type
        }
        bad = jose_jwt.encode(payload, os.environ["SECRET_KEY"], algorithm="HS256")
        r = platform_client.get("/api/auth/me", headers=_bearer(bad))
        assert r.status_code == 401


# ===========================================================================
# Cross-user isolation  (the most critical tests)
# ===========================================================================

class TestCrossUserIsolation:
    def test_user_a_token_cannot_see_user_b_identity(self, platform_client, platform_db):
        email_a = _reg_verify(platform_client, platform_db)
        email_b = _reg_verify(platform_client, platform_db)
        tokens_a = _login(platform_client, email_a)
        r = platform_client.get("/api/auth/me", headers=_bearer(tokens_a["access_token"]))
        assert r.status_code == 200
        assert r.json()["email"] == email_a
        assert r.json()["email"] != email_b

    def test_forged_user_id_in_token_is_401(self, platform_client):
        """A valid JWT with a non-existent user_id must be rejected."""
        fake_token = create_access_token(str(uuid.uuid4()))
        r = platform_client.get("/api/auth/me", headers=_bearer(fake_token))
        assert r.status_code == 401

    def test_refresh_token_returns_correct_users_identity(self, platform_client, platform_db):
        email_a = _reg_verify(platform_client, platform_db)
        email_b = _reg_verify(platform_client, platform_db)
        uid_a = _uid(platform_db, email_a)
        uid_b = _uid(platform_db, email_b)
        tokens_b = _login(platform_client, email_b)

        # Use user B's refresh token — result must identify user B, not A
        r = platform_client.post("/api/auth/refresh", json={"refresh_token": tokens_b["refresh_token"]})
        assert r.status_code == 200
        from jose import jwt as jose_jwt
        payload = jose_jwt.decode(r.json()["access_token"], os.environ["SECRET_KEY"], algorithms=["HS256"])
        assert payload["sub"] == uid_b
        assert payload["sub"] != uid_a

    def test_fake_reset_token_cannot_change_another_users_password(self, platform_client, platform_db):
        email_b = _reg_verify(platform_client, platform_db)
        uid_b = _uid(platform_db, email_b)
        # Insert a real reset token for B — but attacker uses a different fake raw value
        _insert_token(platform_db, uid_b, "password_reset")
        fake_raw = generate_opaque_token()
        r = platform_client.post(
            "/api/auth/password-reset/confirm",
            json={"token": fake_raw, "new_password": "Hacked999!"},
        )
        assert r.status_code == 400
        # B's original password still works
        r2 = platform_client.post("/api/auth/login", json={"email": email_b, "password": "Password1!"})
        assert r2.status_code == 200
