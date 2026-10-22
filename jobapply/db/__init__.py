"""jobapply.db — SQLModel table definitions and database session factory.

This package contains:
  - models.py  : all SQLModel table classes (imported by alembic/env.py)
  - session.py : async session factory and get_db FastAPI dependency

The existing single-user SQLite components (jobapply.ledger,
jobapply.workspace) are not touched; they continue to work for CLI flows.
This package is used exclusively by the multi-user web platform routes.
"""
