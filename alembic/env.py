"""Alembic environment configuration.

Reads DATABASE_URL from the environment at runtime so no credentials are
hard-coded in this file or in alembic.ini.

Supports both online mode (direct PostgreSQL connection) and offline mode
(SQL script generation) via the standard Alembic run_migrations_online /
run_migrations_offline pattern.

The target_metadata is imported from jobapply.db.models so that Alembic's
autogenerate can detect schema drift between the SQLAlchemy models and the
live database.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Import all SQLModel table classes so their metadata is registered before
# Alembic inspects target_metadata.  The star import is intentional and is
# the standard Alembic pattern for SQLModel projects.
# ---------------------------------------------------------------------------
from jobapply.db.models import *  # noqa: F401, F403
from sqlmodel import SQLModel

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to values in alembic.ini.
# ---------------------------------------------------------------------------
config = context.config

# Inject DATABASE_URL from the environment — but only if not already set
# via cfg.set_main_option() (e.g. from conftest.py in tests).
_existing_url = config.get_main_option("sqlalchemy.url")
if not _existing_url:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set.\n"
            "Example: export DATABASE_URL='postgresql+psycopg://user:pass@localhost:5432/jobapply'\n"
            "For local dev: export DATABASE_URL='sqlite:///./jobapply_dev.db'"
        )
    config.set_main_option("sqlalchemy.url", database_url)

# Set up Python logging from the alembic.ini [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata that Alembic uses for autogenerate comparisons.
target_metadata = SQLModel.metadata


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates a SQL script instead of connecting to the database.  Useful
    for reviewing what will be executed or for environments where a direct
    DB connection is not available at migration time.

    Usage:
        alembic upgrade head --sql > migration.sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Include schemas so cross-schema references are handled correctly.
        include_schemas=True,
        # Compare server defaults so migrations detect DEFAULT changes.
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (direct DB connection).

    This is the standard mode used by `alembic upgrade head` and
    `alembic downgrade`.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # NullPool: no persistent connections during migrations
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
