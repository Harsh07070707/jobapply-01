"""Database session factory and FastAPI dependency.

Usage in route handlers
-----------------------
    from jobapply.db.session import get_db
    from sqlalchemy.ext.asyncio import AsyncSession

    @router.get("/api/example")
    async def example(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        result = await db.execute(
            select(Job).where(Job.user_id == current_user.user_id)
        )
        ...

Configuration
-------------
Set DATABASE_URL in the environment before starting the server:

    # PostgreSQL (production / staging)
    export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/jobapply"

    # SQLite (local development only — do not use for multi-user deployments)
    export DATABASE_URL="sqlite+aiosqlite:///./jobapply_dev.db"

The engine is created once at import time and reused across requests via
the connection pool.  The get_db dependency yields a new session per
request and closes it automatically whether the request succeeds or fails.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

_DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

if not _DATABASE_URL:
    import warnings
    warnings.warn(
        "DATABASE_URL is not set. The async database engine has not been "
        "initialized. Set DATABASE_URL before starting the web server.\n"
        "Example: export DATABASE_URL='postgresql+psycopg://user:pass@localhost/jobapply'",
        stacklevel=2,
    )
    # Provide a non-functional placeholder so imports don't fail at module
    # load time in CLI contexts where the DB is not needed.
    _DATABASE_URL = "sqlite+aiosqlite:///./jobapply_dev.db"

# Use NullPool for short-lived connections (e.g. during migrations or testing).
# For production, remove NullPool and let SQLAlchemy manage a connection pool.
_engine = create_async_engine(
    _DATABASE_URL,
    echo=False,           # set to True to log all SQL (useful for debugging)
    future=True,
    poolclass=NullPool,   # swap to default pool in production for performance
)

_AsyncSessionLocal = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # prevents "DetachedInstanceError" after commit
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session; close it after the request completes.

    Always use this as a FastAPI dependency — never create sessions manually
    in route handlers.  The session is automatically rolled back on
    exception and closed on exit.

    Example::

        @router.get("/api/jobs")
        async def list_jobs(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with _AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Sync session factory (used by Alembic and CLI utilities that are not async)
# ---------------------------------------------------------------------------


def get_sync_engine():  # type: ignore[return]
    """Return a synchronous SQLAlchemy engine for Alembic and CLI scripts.

    This is intentionally separate from the async engine used by the web
    server.  Do not use this in FastAPI route handlers.
    """
    from sqlalchemy import create_engine

    sync_url = _DATABASE_URL.replace("+aiosqlite", "").replace("+asyncpg", "")
    return create_engine(sync_url, echo=False, poolclass=NullPool)
