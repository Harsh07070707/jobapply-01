"""Password hashing and verification using bcrypt directly.

passlib's bcrypt backend is incompatible with bcrypt>=4.0 due to a
breaking change in the bcrypt library's 72-byte enforcement.  This
module uses the bcrypt library directly to avoid that conflict.

bcrypt has a 72-byte input limit.  Passwords longer than 72 bytes are
pre-hashed with SHA-256 (producing a 64-byte hex digest) before bcrypt
processing.  This is the standard mitigation and does not weaken security
for passwords of normal length.

Usage
-----
    from jobapply.auth.passwords import hash_password, verify_password

    stored = hash_password("secret123")
    ok     = verify_password("secret123", stored)  # True
    bad    = verify_password("wrong",     stored)  # False
"""

from __future__ import annotations

import hashlib

import bcrypt

# Work factor 12 is the current OWASP minimum recommendation.
_ROUNDS = 12
_MAX_BYTES = 72


def _prepare(plain: str) -> bytes:
    """Return a bcrypt-safe byte string for *plain*.

    If the UTF-8 encoding of *plain* exceeds 72 bytes, pre-hash with
    SHA-256 so the bcrypt input is always exactly 64 ASCII bytes.
    """
    encoded = plain.encode("utf-8")
    if len(encoded) > _MAX_BYTES:
        encoded = hashlib.sha256(encoded).hexdigest().encode("ascii")
    return encoded


def hash_password(plain: str) -> str:
    """Return the bcrypt hash of *plain* as a UTF-8 string for DB storage."""
    return bcrypt.hashpw(_prepare(plain), bcrypt.gensalt(rounds=_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True when *plain* matches the stored *hashed* digest."""
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("utf-8"))
    except Exception:  # noqa: BLE001 — malformed hash is treated as mismatch
        return False
