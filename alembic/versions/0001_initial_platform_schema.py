"""Initial platform schema.

Creates all tables for the multi-user jobapply platform:
  - users, email_tokens, refresh_tokens
  - user_preferences
  - candidate_profiles, candidate_evidence
  - jobs, job_requirements
  - job_matches
  - resume_versions, resume_validations
  - applications, application_events, approvals
  - audit_events, export_requests

This migration is additive: it does not touch the existing single-user
SQLite tables (jobs_ledger, workspace_jobs, workspace_searches) used by
the CLI.  Those tables live in separate local .db files and are managed
by SQLModel.metadata.create_all() at runtime, not by Alembic.

Dialect compatibility
---------------------
The migration runs on both PostgreSQL (production) and SQLite (local
dev / CI).  Two differences are handled transparently by helpers at the
top of this file:

  _jsonb()          — returns JSONB on PostgreSQL, JSON on SQLite
  _json_default()   — returns '[]'::jsonb / '{}'::jsonb on PostgreSQL,
                      '[]' / '{}' on SQLite (SQLite rejects :: casts)

Revision ID: 0001
Revises: (none — this is the initial migration)
Create Date: 2026-10-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Dialect-aware helpers
# ---------------------------------------------------------------------------


def _is_sqlite() -> bool:
    """True when the current Alembic connection is SQLite."""
    bind = op.get_bind()
    return bind.dialect.name == "sqlite"


def _jsonb() -> sa.types.TypeEngine:
    """JSONB on PostgreSQL, JSON on SQLite."""
    if _is_sqlite():
        return sa.JSON()
    return postgresql.JSONB(astext_type=sa.Text())


def _json_default(value: str) -> sa.TextClause:
    """Server default for a JSON/JSONB column.

    PostgreSQL: uses the ``::jsonb`` cast (e.g. ``'[]'::jsonb``).
    SQLite:     plain JSON literal (e.g. ``'[]'``).
    """
    if _is_sqlite():
        return sa.text(f"'{value}'")
    return sa.text(f"'{value}'::jsonb")


def _ts_default() -> sa.TextClause:
    """now() on PostgreSQL, CURRENT_TIMESTAMP on SQLite."""
    if _is_sqlite():
        return sa.text("CURRENT_TIMESTAMP")
    return sa.text("now()")


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("user_id", sa.Text(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("email_verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.CheckConstraint(
            "status IN ('active','suspended','deleted')",
            name="ck_users_status",
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ------------------------------------------------------------------
    # email_tokens
    # ------------------------------------------------------------------
    op.create_table(
        "email_tokens",
        sa.Column("token_id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.CheckConstraint(
            "purpose IN ('email_verification','password_reset')",
            name="ck_email_tokens_purpose",
        ),
        sa.UniqueConstraint("token_hash", name="uq_email_tokens_hash"),
    )
    op.create_index("ix_email_tokens_user_id", "email_tokens", ["user_id"])

    # ------------------------------------------------------------------
    # refresh_tokens
    # ------------------------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("token_id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    # ------------------------------------------------------------------
    # user_preferences
    # ------------------------------------------------------------------
    op.create_table(
        "user_preferences",
        sa.Column("pref_id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_roles",
            _jsonb(),
            nullable=False,
            server_default=_json_default("[]"),
        ),
        sa.Column(
            "locations",
            _jsonb(),
            nullable=False,
            server_default=_json_default("[]"),
        ),
        sa.Column(
            "remote_preference",
            sa.Text(),
            nullable=False,
            server_default="any",
        ),
        sa.Column(
            "employment_types",
            _jsonb(),
            nullable=False,
            server_default=_json_default("[]"),
        ),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.Text(), nullable=False, server_default="INR"),
        sa.Column("work_authorization", sa.Text(), nullable=False, server_default=""),
        sa.Column("notice_period_days", sa.Integer(), nullable=True),
        sa.Column(
            "score_threshold", sa.Float(), nullable=False, server_default="35.0"
        ),
        sa.Column(
            "preferred_sites",
            _jsonb(),
            nullable=False,
            server_default=_json_default("[]"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.CheckConstraint(
            "remote_preference IN ('remote','hybrid','onsite','any')",
            name="ck_user_prefs_remote",
        ),
        sa.UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"])

    # ------------------------------------------------------------------
    # candidate_profiles
    # ------------------------------------------------------------------
    op.create_table(
        "candidate_profiles",
        sa.Column("profile_id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("profile_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "profile_json",
            _jsonb(),
            nullable=False,
            server_default=_json_default("{}"),
        ),
        sa.Column("source_file_ref", sa.Text(), nullable=True),
        sa.Column("source_file_type", sa.Text(), nullable=True),
        sa.Column(
            "parse_status", sa.Text(), nullable=False, server_default="pending"
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.CheckConstraint(
            "source_file_type IN ('pdf','docx') OR source_file_type IS NULL",
            name="ck_profiles_file_type",
        ),
        sa.CheckConstraint(
            "parse_status IN ('pending','parsed','failed')",
            name="ck_profiles_parse_status",
        ),
        sa.UniqueConstraint(
            "user_id", "profile_version", name="uq_profiles_user_version"
        ),
    )
    op.create_index("ix_candidate_profiles_user_id", "candidate_profiles", ["user_id"])

    # ------------------------------------------------------------------
    # candidate_evidence
    # ------------------------------------------------------------------
    op.create_table(
        "candidate_evidence",
        sa.Column("evidence_id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Text(),
            sa.ForeignKey("candidate_profiles.profile_id"),
            nullable=False,
        ),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column(
            "verification_status",
            sa.Text(),
            nullable=False,
            server_default="unverified",
        ),
        sa.Column(
            "allowed_use", sa.Boolean(), nullable=False, server_default="0"
        ),
        sa.Column(
            "job_requirements",
            _jsonb(),
            nullable=False,
            server_default=_json_default("[]"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.Column("verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "verification_status IN ('unverified','verified','contradicted','user_approved')",
            name="ck_evidence_status",
        ),
        # Contract 1 safety net at DB level.
        sa.CheckConstraint(
            "(allowed_use = 0 OR allowed_use = false) OR "
            "verification_status IN ('verified','user_approved')",
            name="ck_evidence_allowed_use_consistent",
        ),
    )
    op.create_index("ix_candidate_evidence_user_id", "candidate_evidence", ["user_id"])
    op.create_index(
        "ix_candidate_evidence_profile_id", "candidate_evidence", ["profile_id"]
    )

    # ------------------------------------------------------------------
    # jobs
    # ------------------------------------------------------------------
    op.create_table(
        "jobs",
        sa.Column("job_id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False, server_default=""),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("location", sa.Text(), nullable=False, server_default=""),
        sa.Column("employment_type", sa.Text(), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("apply_url", sa.Text(), nullable=True),
        sa.Column("posting_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column(
            "raw_json",
            _jsonb(),
            nullable=False,
            server_default=_json_default("{}"),
        ),
        sa.CheckConstraint(
            "status IN ('active','expired','closed','removed')",
            name="ck_jobs_status",
        ),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_user_status", "jobs", ["user_id", "status"])
    # Partial unique index: per-source dedup — only when external_id is present.
    # SQLite supports partial indexes from version 3.8.9+.
    op.create_index(
        "ix_jobs_source_dedup",
        "jobs",
        ["user_id", "source_name", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
        sqlite_where=sa.text("external_id IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # job_requirements
    # ------------------------------------------------------------------
    op.create_table(
        "job_requirements",
        sa.Column("req_id", sa.Text(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Text(),
            sa.ForeignKey("jobs.job_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column("normalized_term", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False, server_default="skill"),
        sa.Column("importance", sa.Text(), nullable=False, server_default="preferred"),
        sa.Column(
            "extracted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.Column(
            "user_reclassified",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.CheckConstraint(
            "category IN ('skill','experience','education','location','work_auth','other')",
            name="ck_requirements_category",
        ),
        sa.CheckConstraint(
            "importance IN ('required','preferred','disqualifying')",
            name="ck_requirements_importance",
        ),
    )
    op.create_index("ix_job_requirements_job_id", "job_requirements", ["job_id"])
    op.create_index("ix_job_requirements_user_id", "job_requirements", ["user_id"])

    # ------------------------------------------------------------------
    # job_matches
    # ------------------------------------------------------------------
    op.create_table(
        "job_matches",
        sa.Column("match_id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.Text(),
            sa.ForeignKey("jobs.job_id"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Text(),
            sa.ForeignKey("candidate_profiles.profile_id"),
            nullable=False,
        ),
        sa.Column(
            "scoring_model_version",
            sa.Text(),
            nullable=False,
            server_default="1.0",
        ),
        sa.Column("score_required_skills", sa.Float(), nullable=True),
        sa.Column("score_experience", sa.Float(), nullable=True),
        sa.Column("score_role_relevance", sa.Float(), nullable=True),
        sa.Column("score_preferred_skills", sa.Float(), nullable=True),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.Column("mandatory_pass", sa.Boolean(), nullable=True),
        sa.Column(
            "mandatory_failures",
            _jsonb(),
            nullable=False,
            server_default=_json_default("[]"),
        ),
        sa.Column(
            "explanation",
            _jsonb(),
            nullable=False,
            server_default=_json_default("{}"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
    )
    op.create_index("ix_job_matches_user_job", "job_matches", ["user_id", "job_id"])

    # ------------------------------------------------------------------
    # resume_versions
    # ------------------------------------------------------------------
    op.create_table(
        "resume_versions",
        sa.Column("resume_version_id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.Text(),
            sa.ForeignKey("jobs.job_id"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Text(),
            sa.ForeignKey("candidate_profiles.profile_id"),
            nullable=False,
        ),
        sa.Column(
            "match_id",
            sa.Text(),
            sa.ForeignKey("job_matches.match_id"),
            nullable=True,
        ),
        sa.Column(
            "template_version", sa.Text(), nullable=False, server_default="1.0"
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column(
            "resume_json",
            _jsonb(),
            nullable=False,
            server_default=_json_default("{}"),
        ),
        sa.Column("file_ref", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ("
            "'draft','generated','validating','validation_failed',"
            "'ready_for_review','user_approved_for_application',"
            "'superseded','deleted')",
            name="ck_resume_versions_status",
        ),
    )
    op.create_index("ix_resume_versions_user_id", "resume_versions", ["user_id"])
    op.create_index(
        "ix_resume_versions_user_job", "resume_versions", ["user_id", "job_id"]
    )

    # ------------------------------------------------------------------
    # resume_validations
    # ------------------------------------------------------------------
    op.create_table(
        "resume_validations",
        sa.Column("validation_id", sa.Text(), primary_key=True),
        sa.Column(
            "resume_version_id",
            sa.Text(),
            sa.ForeignKey("resume_versions.resume_version_id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pdf_extraction_ok", sa.Boolean(), nullable=False, server_default="0"
        ),
        sa.Column(
            "integrity_ok", sa.Boolean(), nullable=False, server_default="0"
        ),
        sa.Column(
            "unsupported_claims",
            _jsonb(),
            nullable=False,
            server_default=_json_default("[]"),
        ),
        sa.Column(
            "keyword_coverage",
            _jsonb(),
            nullable=False,
            server_default=_json_default("{}"),
        ),
        sa.Column(
            "layout_warnings",
            _jsonb(),
            nullable=False,
            server_default=_json_default("[]"),
        ),
        sa.Column(
            "overall_status", sa.Text(), nullable=False, server_default="pending"
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.CheckConstraint(
            "overall_status IN ('pending','pass','fail')",
            name="ck_resume_validations_status",
        ),
    )
    op.create_index(
        "ix_resume_validations_resume_version_id",
        "resume_validations",
        ["resume_version_id"],
    )

    # ------------------------------------------------------------------
    # applications
    # ------------------------------------------------------------------
    op.create_table(
        "applications",
        sa.Column("application_id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.Text(),
            sa.ForeignKey("jobs.job_id"),
            nullable=False,
        ),
        sa.Column(
            "resume_version_id",
            sa.Text(),
            sa.ForeignKey("resume_versions.resume_version_id"),
            nullable=True,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="discovered"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.CheckConstraint(
            "status IN ("
            "'discovered','normalized','matched','resume_generating',"
            "'resume_validating','resume_ready','pending_user_review',"
            "'application_prepared','pending_approval','user_submitted',"
            "'failed','expired','closed')",
            name="ck_applications_status",
        ),
        sa.UniqueConstraint("user_id", "job_id", name="uq_applications_user_job"),
    )
    op.create_index("ix_applications_user_id", "applications", ["user_id"])

    # ------------------------------------------------------------------
    # application_events (append-only)
    # ------------------------------------------------------------------
    op.create_table(
        "application_events",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Text(),
            sa.ForeignKey("applications.application_id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            _jsonb(),
            nullable=False,
            server_default=_json_default("{}"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
    )
    op.create_index(
        "ix_application_events_application_id",
        "application_events",
        ["application_id"],
    )
    op.create_index(
        "ix_application_events_user_id", "application_events", ["user_id"]
    )

    # ------------------------------------------------------------------
    # approvals  (Contract 3 record)
    # ------------------------------------------------------------------
    op.create_table(
        "approvals",
        sa.Column("approval_id", sa.Text(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Text(),
            sa.ForeignKey("applications.application_id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "approved_resume_version_id",
            sa.Text(),
            sa.ForeignKey("resume_versions.resume_version_id"),
            nullable=False,
        ),
        sa.Column(
            "user_confirmed_submission",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "approved_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.Column("url_opened_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("external_reference", sa.Text(), nullable=True),
        sa.UniqueConstraint("application_id", name="uq_approvals_application_id"),
    )
    op.create_index("ix_approvals_application_id", "approvals", ["application_id"])
    op.create_index("ix_approvals_user_id", "approvals", ["user_id"])

    # ------------------------------------------------------------------
    # audit_events
    # ------------------------------------------------------------------
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=True),
        sa.Column("resource_id", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
    )
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    # ------------------------------------------------------------------
    # export_requests
    # ------------------------------------------------------------------
    op.create_table(
        "export_requests",
        sa.Column("request_id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("file_ref", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_ts_default(),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','ready','expired','failed')",
            name="ck_export_requests_status",
        ),
    )
    op.create_index("ix_export_requests_user_id", "export_requests", ["user_id"])


# ---------------------------------------------------------------------------
# Downgrade — drop all tables in reverse dependency order
# ---------------------------------------------------------------------------


def downgrade() -> None:
    op.drop_table("export_requests")
    op.drop_table("audit_events")
    op.drop_table("approvals")
    op.drop_table("application_events")
    op.drop_table("applications")
    op.drop_table("resume_validations")
    op.drop_table("resume_versions")
    op.drop_table("job_matches")
    op.drop_table("job_requirements")
    op.drop_table("jobs")
    op.drop_table("candidate_evidence")
    op.drop_table("candidate_profiles")
    op.drop_table("user_preferences")
    op.drop_table("refresh_tokens")
    op.drop_table("email_tokens")
    op.drop_table("users")
