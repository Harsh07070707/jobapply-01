"""JWT token creation / decoding and raw-token hashing.

Access tokens
-------------
Short-lived (default 15 min) signed JWTs carried in the Authorization
header.  They are stateless — the server does not store them.

Refresh tokens
--------------
Long-lived (default 7 days) opaque random strings.  Only their SHA-256
hash is stored in refresh_tokens so a stolen database dump cannot be
used to forge sessions.

Email tokens (verification / password-reset)
--------------------------------------------
Same hash-only approach as refresh tokens.  A random URL-safe string is
returned to the caller (to be emailed); only its SHA-256 hash is stored.

Configuration (environment variables)
--------------------------------------
SECRET_KEY                      Required.  Used to sign JWTs.
ACCESS_TOKEN_EXPIRE_SECONDS     Optional.  Default 900 (15 min).
REFRESH_TOKEN_EXPIRE_SECONDS    Optional.  Default 604800 (7 days).
EMAIL_TOKEN_EXPIRE_SECONDS      Optional.  Default 86400 (24 h).
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
_ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_SECONDS: int = int(
    os.environ.get("ACCESS_TOKEN_EXPIRE_SECONDS", "900")
)
REFRESH_TOKEN_EXPIRE_SECONDS: int = int(
    os.environ.get("REFRESH_TOKEN_EXPIRE_SECONDS", "604800")
)
EMAIL_TOKEN_EXPIRE_SECONDS: int = int(
    os.environ.get("EMAIL_TOKEN_EXPIRE_SECONDS", "86400")
)


def _secret() -> str:
    """Return SECRET_KEY, raising clearly if it is not set."""
    key = _SECRET_KEY or os.environ.get("SECRET_KEY", "")
    if not key:
        raise RuntimeError(
            "SECRET_KEY environment variable is not set. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return key


# ---------------------------------------------------------------------------
# JWT — access tokens
# ---------------------------------------------------------------------------


def create_access_token(user_id: str) -> str:
    """Return a signed JWT access token for *user_id*.

    The token payload contains:
      sub  — user_id (string)
      exp  — expiry timestamp
      iat  — issued-at timestamp
      type — 'access'
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "exp": now + timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS),
        "iat": now,
        "type": "access",
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token.

    Returns the payload dict on success.
    Raises ``jose.JWTError`` on expiry, bad signature, or wrong type.
    """
    payload = jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Token is not an access token")
    return payload


# ---------------------------------------------------------------------------
# Opaque tokens — refresh / email
# ---------------------------------------------------------------------------


def generate_opaque_token() -> str:
    """Return a 48-byte URL-safe random token string (64 chars).

    This is the raw value sent to the user (in a cookie or email link).
    Never store this — store only its hash via :func:`hash_token`.
    """
    return secrets.token_urlsafe(48)


def hash_token(raw: str) -> str:
    """Return the SHA-256 hex digest of *raw*.

    This is what gets stored in the database.
    """
    return hashlib.sha256(raw.encode()).hexdigest()


def token_expiry(expire_seconds: int) -> datetime:
    """Return a UTC datetime *expire_seconds* from now."""
    return datetime.now(timezone.utc) + timedelta(seconds=expire_seconds)
