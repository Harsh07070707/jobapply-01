"""FastAPI dependencies for authentication and database access.

Usage in route handlers
-----------------------
    from jobapply.auth.dependencies import get_current_user, get_db
    from sqlalchemy.orm import Session

    @router.get("/api/jobs")
    def list_jobs(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        # Every query MUST be scoped to current_user.user_id
        jobs = db.execute(
            select(Job).where(Job.user_id == current_user.user_id)
        ).scalars().all()

Security rules enforced here
-----------------------------
- Bearer token must be present, valid, and not expired.
- Token type must be 'access' (refresh tokens are rejected).
- User must exist in the database and have status='active'.
- User's email must be verified (email_verified_at IS NOT NULL).
  Unverified users get 403, not 401, so they know to check their inbox.
- Return 404 (not 403) on cross-user resource access so existence
  of other users' records is never leaked.  This rule is enforced in
  individual route handlers, not here.
"""

from __future__ import annotations

import os
from collections.abc import Generator

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from jobapply.auth.tokens import decode_access_token

_bearer = HTTPBearer(auto_error=True)

# ---------------------------------------------------------------------------
# Lazy engine — built on first use so DATABASE_URL can be set after import
# ---------------------------------------------------------------------------

_engine = None
_SessionLocal = None


def _get_session_factory():
    """Return (and lazily create) the session factory.

    Building the engine here instead of at module level means tests can
    set DATABASE_URL *before* the first request and get the correct DB.
    """
    global _engine, _SessionLocal
    if _SessionLocal is None:
        database_url = os.environ.get("DATABASE_URL", "sqlite:///./jobapply_platform.db")
        sync_url = (
            database_url
            .replace("postgresql+psycopg://", "postgresql+psycopg2://")
            .replace("sqlite+aiosqlite://", "sqlite://")
        )
        _engine = create_engine(
            sync_url,
            connect_args={"check_same_thread": False} if "sqlite" in sync_url else {},
            pool_pre_ping=True,
        )
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a synchronous SQLAlchemy session; close it after the request."""
    db = _get_session_factory()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Thin user dict — avoids importing SQLModel inside every route handler.
# Routes receive a plain dict; they access user_id, email, status.
# ---------------------------------------------------------------------------

def _fetch_user(db: Session, user_id: str) -> dict | None:
    row = db.execute(
        text("SELECT user_id, email, status, email_verified_at FROM users WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchone()
    if row is None:
        return None
    return {
        "user_id": str(row.user_id),
        "email": str(row.email),
        "status": str(row.status),
        "email_verified_at": row.email_verified_at,
    }


# ---------------------------------------------------------------------------
# get_current_user dependency
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    db: Session = Depends(get_db),
) -> dict:
    """Validate the Bearer token and return the authenticated user dict.

    Raises:
        401 — token missing, malformed, expired, or wrong type
        403 — user inactive or email not yet verified
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = _fetch_user(db, user_id)
    if user is None:
        raise credentials_exception

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

    return user


def get_current_user_unverified(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    db: Session = Depends(get_db),
) -> dict:
    """Like get_current_user but allows unverified email.

    Used only by GET /api/auth/me so users can check their verification
    status after registration without being locked out.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = _fetch_user(db, user_id)
    if user is None:
        raise credentials_exception

    if user["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended or deleted.",
        )

    return user
