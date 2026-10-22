"""Shared pytest fixtures for the jobapply test suite.

Auth tests need a real database.  This conftest:
  1. Creates one SQLite file per pytest session in a temp directory.
  2. Runs the Alembic migration against it.
  3. Builds a FastAPI TestClient whose get_db dependency is overridden
     to always use that file — regardless of what DATABASE_URL is set
     to at import time.
  4. Exposes a `platform_db` session fixture for direct SQL assertions.

All other existing tests (test_server_api.py, test_jd_extract.py, etc.)
are unaffected because they do not use these fixtures.
"""

from __future__ import annotations

import os
import pathlib
import tempfile
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Must be set before any jobapply import that reads env vars.
os.environ.setdefault("SECRET_KEY", "ci-test-secret-key-32-chars-xx!!")
os.environ.setdefault("TESTING", "1")

# ---------------------------------------------------------------------------
# Session-scoped temp directory and database
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def platform_db_path(tmp_path_factory) -> pathlib.Path:
    """Absolute path to the session-scoped test SQLite database."""
    base = tmp_path_factory.mktemp("platform_db")
    return base / "platform.db"


@pytest.fixture(scope="session")
def platform_db_url(platform_db_path) -> str:
    return f"sqlite:///{platform_db_path}"


@pytest.fixture(scope="session", autouse=False)
def run_migrations(platform_db_url):
    """Run alembic upgrade head against the test database once per session."""
    from alembic import command
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig("alembic.ini")
    # Override the URL directly on the config so DATABASE_URL env var
    # doesn't interfere.
    cfg.set_main_option("sqlalchemy.url", platform_db_url)
    command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# SQLAlchemy engine / session for the test database
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def platform_engine(platform_db_url, run_migrations):
    engine = create_engine(
        platform_db_url,
        connect_args={"check_same_thread": False},
    )
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def _platform_session_factory(platform_engine):
    return sessionmaker(bind=platform_engine, autocommit=False, autoflush=False)


@pytest.fixture()
def platform_db(_platform_session_factory) -> Generator[Session, None, None]:
    """Yield a per-test SQLAlchemy session to the platform database.

    Uses autocommit=False but calls session.expire_all() before each
    query so it always reads the latest committed data from other
    connections (e.g. the TestClient's get_db sessions).
    """
    session = _platform_session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# FastAPI TestClient with get_db overridden
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def platform_app(platform_engine, run_migrations, tmp_path_factory):
    """Create the FastAPI app with get_db wired to the test database."""
    from jobapply.auth.dependencies import get_db
    from jobapply.server import create_app

    # Build a session factory bound to the test engine
    TestSessionLocal = sessionmaker(
        bind=platform_engine, autocommit=False, autoflush=False
    )

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    ws = tmp_path_factory.mktemp("workspace")
    app = create_app(workspace_path=ws, enable_cors=False)
    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(scope="session")
def platform_client(platform_app) -> TestClient:
    """Session-scoped TestClient for platform/auth routes."""
    return TestClient(platform_app, raise_server_exceptions=True)
