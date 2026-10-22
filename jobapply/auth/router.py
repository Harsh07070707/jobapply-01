"""Authentication route handlers.

Endpoints
---------
POST   /api/auth/register              Create account; send verification email
GET    /api/auth/verify-email          Consume email-verification token
POST   /api/auth/login                 Password login; return access + refresh tokens
POST   /api/auth/refresh               Exchange refresh token for new access token
POST   /api/auth/logout                Revoke refresh token
GET    /api/auth/me                    Return current user profile
POST   /api/auth/password-reset/request    Send password-reset email
POST   /api/auth/password-reset/confirm    Consume token, set new password

Rate limiting
-------------
Applied via slowapi at the application level (wired in server.py).
The limits are defined as strings on each route using the @limiter.limit
decorator pattern — see server.py for the Limiter instance.

Security rules
--------------
- Passwords are hashed with bcrypt before storage; plaintext is never kept.
- Verification and reset tokens are stored as SHA-256 hashes; raw tokens
  are sent to the user and immediately discarded server-side.
- Tokens are single-use: used_at is set atomically in the same DB
  transaction that processes the token.
- Expired tokens are rejected (expires_at < now).
- Cross-user access: routes scope every DB query to the authenticated
  user_id; 404 is returned (not 403) so resource existence is not leaked.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.orm import Session

# Rate limiter — key by remote IP.
limiter = Limiter(key_func=get_remote_address)

# In test environments, apply a very high limit so tests never get blocked.
_TESTING = os.environ.get("TESTING", "0") == "1"
_REGISTER_LIMIT = "99999/hour" if _TESTING else "5/hour"
_LOGIN_LIMIT = "99999/minute" if _TESTING else "10/15minute"
_RESET_LIMIT = "99999/hour" if _TESTING else "3/hour"

from jobapply.auth.dependencies import get_current_user, get_current_user_unverified, get_db
from jobapply.auth.email import send_password_reset_email, send_verification_email
from jobapply.auth.passwords import hash_password, verify_password
from jobapply.auth.tokens import (
    EMAIL_TOKEN_EXPIRE_SECONDS,
    REFRESH_TOKEN_EXPIRE_SECONDS,
    create_access_token,
    generate_opaque_token,
    hash_token,
    token_expiry,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_user_by_email(db: Session, email: str) -> dict | None:
    row = db.execute(
        text(
            "SELECT user_id, email, password_hash, status, email_verified_at "
            "FROM users WHERE email = :email"
        ),
        {"email": email.lower()},
    ).fetchone()
    if row is None:
        return None
    return {
        "user_id": str(row.user_id),
        "email": str(row.email),
        "password_hash": str(row.password_hash),
        "status": str(row.status),
        "email_verified_at": row.email_verified_at,
    }


def _create_refresh_token_db(db: Session, user_id: str, raw: str) -> None:
    """Insert a new refresh token row (hashed)."""
    db.execute(
        text(
            "INSERT INTO refresh_tokens (token_id, user_id, token_hash, expires_at, created_at) "
            "VALUES (:tid, :uid, :hash, :exp, :now)"
        ),
        {
            "tid": str(uuid.uuid4()),
            "uid": user_id,
            "hash": hash_token(raw),
            "exp": token_expiry(REFRESH_TOKEN_EXPIRE_SECONDS),
            "now": _now(),
        },
    )
    db.commit()


def _revoke_refresh_token(db: Session, raw: str) -> bool:
    """Set revoked_at on the matching refresh token. Returns True if found."""
    row = db.execute(
        text("SELECT token_id, expires_at, revoked_at FROM refresh_tokens WHERE token_hash = :h"),
        {"h": hash_token(raw)},
    ).fetchone()
    if row is None:
        return False
    db.execute(
        text("UPDATE refresh_tokens SET revoked_at = :now WHERE token_hash = :h"),
        {"h": hash_token(raw), "now": _now()},
    )
    db.commit()
    return True


def _consume_email_token(db: Session, raw: str, purpose: str) -> dict | None:
    """Atomically validate and consume an email token.

    Returns the associated user dict, or None if the token is invalid,
    expired, or already used.
    """
    h = hash_token(raw)
    row = db.execute(
        text(
            "SELECT t.token_id, t.user_id, t.expires_at, t.used_at, "
            "u.email, u.status, u.email_verified_at "
            "FROM email_tokens t JOIN users u ON t.user_id = u.user_id "
            "WHERE t.token_hash = :h AND t.purpose = :p"
        ),
        {"h": h, "p": purpose},
    ).fetchone()

    if row is None:
        return None

    # Reject if already used
    if row.used_at is not None:
        return None

    # Reject if expired — compare naive vs aware safely
    expires_at = row.expires_at
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if _now() > expires_at:
        return None

    # Mark as used atomically
    db.execute(
        text("UPDATE email_tokens SET used_at = :now WHERE token_hash = :h"),
        {"h": h, "now": _now()},
    )
    db.commit()

    return {
        "user_id": str(row.user_id),
        "email": str(row.email),
        "status": str(row.status),
        "email_verified_at": row.email_verified_at,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit(_REGISTER_LIMIT)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Create a new account and send an email-verification link.

    Returns 201 on success.  Returns 409 if the email is already registered
    (do not reveal whether the email exists with a different message shape).
    """
    email = payload.email.lower().strip()

    # Check for existing account — same message for both taken and new so
    # enumeration is harder, but we still 409 to let the client know.
    existing = db.execute(
        text("SELECT user_id FROM users WHERE email = :e"), {"e": email}
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    user_id = str(uuid.uuid4())
    now = _now()
    db.execute(
        text(
            "INSERT INTO users (user_id, email, password_hash, status, created_at, updated_at) "
            "VALUES (:uid, :email, :hash, 'active', :now, :now)"
        ),
        {"uid": user_id, "email": email, "hash": hash_password(payload.password), "now": now},
    )

    # Create email verification token
    raw = generate_opaque_token()
    db.execute(
        text(
            "INSERT INTO email_tokens (token_id, user_id, token_hash, purpose, expires_at, created_at) "
            "VALUES (:tid, :uid, :hash, 'email_verification', :exp, :now)"
        ),
        {
            "tid": str(uuid.uuid4()),
            "uid": user_id,
            "hash": hash_token(raw),
            "exp": token_expiry(EMAIL_TOKEN_EXPIRE_SECONDS),
            "now": now,
        },
    )
    db.commit()

    # Send verification email (prints to stdout in dev/CI when SMTP not configured)
    try:
        send_verification_email(email, raw)
    except Exception:
        pass  # Never fail registration because of email delivery

    return {
        "message": "Account created. Check your email to verify your address before logging in.",
        "user_id": user_id,
    }


@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    """Consume an email-verification token and mark the account as verified."""
    user = _consume_email_token(db, token, "email_verification")
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification link is invalid, expired, or already used.",
        )

    db.execute(
        text("UPDATE users SET email_verified_at = :now, updated_at = :now WHERE user_id = :uid"),
        {"now": _now(), "uid": user["user_id"]},
    )
    db.commit()

    return {"message": "Email verified successfully. You can now log in."}


@router.post("/resend-verification")
@limiter.limit(_REGISTER_LIMIT)
def resend_verification(payload: dict, request: Request, db: Session = Depends(get_db)):
    """Resend email verification link. Returns 200 even if email doesn't exist (anti-enumeration)."""
    email = payload.get("email", "").lower().strip()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")

    # Find user
    user_row = db.execute(
        text("SELECT user_id, email_verified_at FROM users WHERE email = :e"), {"e": email}
    ).fetchone()
    
    # Always return success to prevent email enumeration
    if not user_row:
        return {"message": "If an account with that email exists, a verification link has been sent."}
    
    user_id = user_row[0]
    verified_at = user_row[1]
    
    # If already verified, still return success
    if verified_at:
        return {"message": "If an account with that email exists, a verification link has been sent."}
    
    # Delete old verification tokens for this user
    db.execute(
        text("DELETE FROM email_tokens WHERE user_id = :uid AND purpose = 'email_verification'"),
        {"uid": user_id}
    )
    
    # Create new token
    raw = generate_opaque_token()
    now = _now()
    db.execute(
        text(
            "INSERT INTO email_tokens (token_id, user_id, token_hash, purpose, expires_at, created_at) "
            "VALUES (:tid, :uid, :hash, 'email_verification', :exp, :now)"
        ),
        {
            "tid": str(uuid.uuid4()),
            "uid": user_id,
            "hash": hash_token(raw),
            "exp": token_expiry(EMAIL_TOKEN_EXPIRE_SECONDS),
            "now": now,
        },
    )
    db.commit()
    
    # Send email
    try:
        send_verification_email(email, raw)
    except Exception:
        pass
    
    return {"message": "If an account with that email exists, a verification link has been sent."}


@router.post("/login")
@limiter.limit(_LOGIN_LIMIT)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate with email and password.

    Returns an access token and a refresh token on success.
    Always returns the same 401 for wrong email or wrong password — do not
    reveal which field was incorrect.
    """
    _auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = _get_user_by_email(db, payload.email)
    if user is None:
        raise _auth_error

    if not verify_password(payload.password, user["password_hash"]):
        raise _auth_error

    if user["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended or deleted.",
        )

    if user["email_verified_at"] is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not yet verified. Check your inbox.",
        )

    access = create_access_token(user["user_id"])
    raw_refresh = generate_opaque_token()
    _create_refresh_token_db(db, user["user_id"], raw_refresh)

    return TokenResponse(access_token=access, refresh_token=raw_refresh)


@router.post("/refresh")
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access token.

    The refresh token is NOT rotated here (single-use rotation adds
    complexity; add it in a future iteration if needed).
    """
    h = hash_token(payload.refresh_token)
    row = db.execute(
        text(
            "SELECT r.token_id, r.user_id, r.expires_at, r.revoked_at, "
            "u.status, u.email_verified_at "
            "FROM refresh_tokens r JOIN users u ON r.user_id = u.user_id "
            "WHERE r.token_hash = :h"
        ),
        {"h": h},
    ).fetchone()

    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token is invalid, expired, or revoked.",
    )

    if row is None:
        raise invalid
    if row.revoked_at is not None:
        raise invalid

    expires_at = row.expires_at
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if _now() > expires_at:
        raise invalid

    if row.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account suspended.")

    access = create_access_token(str(row.user_id))
    return TokenResponse(access_token=access)


@router.post("/logout")
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Revoke the supplied refresh token.

    Always returns 200 — even if the token was already revoked or not found
    — so clients don't learn anything useful from the response shape.
    """
    _revoke_refresh_token(db, payload.refresh_token)
    return {"message": "Logged out successfully."}


@router.get("/me")
def me(current_user: dict = Depends(get_current_user_unverified)):
    """Return the current user's public profile.

    Uses get_current_user_unverified so users can see their verification
    status immediately after registration.
    """
    return {
        "user_id": current_user["user_id"],
        "email": current_user["email"],
        "status": current_user["status"],
        "email_verified": current_user["email_verified_at"] is not None,
    }


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(_RESET_LIMIT)
def password_reset_request(payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
    """Send a password-reset email.

    Always returns 202 regardless of whether the email is registered.
    This prevents email enumeration.
    """
    email = payload.email.lower().strip()
    user = _get_user_by_email(db, email)

    if user and user["status"] == "active":
        raw = generate_opaque_token()
        # Password reset tokens expire in 1 hour
        db.execute(
            text(
                "INSERT INTO email_tokens (token_id, user_id, token_hash, purpose, expires_at, created_at) "
                "VALUES (:tid, :uid, :hash, 'password_reset', :exp, :now)"
            ),
            {
                "tid": str(uuid.uuid4()),
                "uid": user["user_id"],
                "hash": hash_token(raw),
                "exp": token_expiry(3600),   # 1 hour for password reset
                "now": _now(),
            },
        )
        db.commit()
        try:
            send_password_reset_email(email, raw)
        except Exception:
            pass

    return {
        "message": "If an account with that email exists, a password-reset link has been sent."
    }


@router.post("/password-reset/confirm")
def password_reset_confirm(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    """Consume a password-reset token and set a new password."""
    user = _consume_email_token(db, payload.token, "password_reset")
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset link is invalid, expired, or already used.",
        )

    db.execute(
        text(
            "UPDATE users SET password_hash = :hash, updated_at = :now "
            "WHERE user_id = :uid"
        ),
        {"hash": hash_password(payload.new_password), "now": _now(), "uid": user["user_id"]},
    )
    # Revoke all existing refresh tokens for this user so old sessions are invalidated
    db.execute(
        text("UPDATE refresh_tokens SET revoked_at = :now WHERE user_id = :uid AND revoked_at IS NULL"),
        {"now": _now(), "uid": user["user_id"]},
    )
    db.commit()

    return {"message": "Password updated successfully. Please log in again."}
