"""SQLModel table definitions for the jobapply multi-user platform.

These models are the single source of truth for the PostgreSQL schema.
Alembic reads them via `jobapply.db.models` (imported as `*` in
alembic/env.py) to generate and validate migrations.

Design rules
------------
- Every user-owned table carries a non-nullable ``user_id`` foreign key.
- Primary keys are UUIDs generated server-side (not auto-increment ints)
  so IDs are not enumerable from the outside.
- Timestamps are stored in UTC; the application layer converts to the
  user's configured timezone for display.
- No resume content, passwords, tokens, or API keys appear in log-safe
  columns — only IDs and status enums are safe to log.
- The three integrity contracts are documented here but enforced in the
  application service layer (not via DB triggers) so they are testable.

Integrity contracts (enforced in application code)
---------------------------------------------------
Contract 1 — Evidence eligibility:
  A JobRequirement may only be scored SUPPORTED when at least one
  CandidateEvidence row matches it with
    verification_status IN ('verified', 'user_approved')
    AND allowed_use = true

Contract 2 — Resume readiness:
  A ResumeVersion may only transition to 'ready_for_review' when:
    (a) pdf_extraction_ok = true
    (b) integrity_ok = true
    (c) unsupported_claims JSON array is empty

Contract 3 — Application submission:
  An Application may only transition to 'user_submitted' when the
  linked Approval row has:
    approved_resume_version_id IS NOT NULL
    AND user_confirmed_submission = true
    AND approved_at IS NOT NULL
  Opening the application URL is a separate event and never triggers
  this transition.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid() -> UUID:
    return uuid4()


def _now() -> datetime:
    from datetime import timezone
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class User(SQLModel, table=True):
    """Registered platform user.

    ``password_hash`` stores the bcrypt/argon2 digest — never the
    plaintext password.  ``email_verified_at`` is null until the user
    clicks the verification link; protected routes must reject requests
    from unverified accounts.
    """

    __tablename__ = "users"  # type: ignore[assignment]

    user_id: UUID = Field(default_factory=_uuid, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=320)
    password_hash: str = Field(max_length=256)
    email_verified_at: Optional[datetime] = Field(default=None)
    status: str = Field(default="active", max_length=20)
    # CHECK: status IN ('active', 'suspended', 'deleted')
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class EmailToken(SQLModel, table=True):
    """Single-use, expiring token for email verification and password reset.

    ``token_hash`` is the SHA-256 digest of the raw token sent to the
    user.  The raw token is never stored.  ``used_at`` non-null means
    the token has been consumed; any second use must be rejected
    atomically in the same transaction that sets ``used_at``.
    """

    __tablename__ = "email_tokens"  # type: ignore[assignment]

    token_id: UUID = Field(default_factory=_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.user_id", index=True)
    token_hash: str = Field(unique=True, max_length=64)
    purpose: str = Field(max_length=32)
    # CHECK: purpose IN ('email_verification', 'password_reset')
    expires_at: datetime
    used_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)


class RefreshToken(SQLModel, table=True):
    """Stored refresh token for the JWT refresh flow.

    Storing refresh tokens server-side allows revocation (logout,
    account suspension).  ``token_hash`` follows the same pattern as
    ``EmailToken``: only the hash is persisted.
    """

    __tablename__ = "refresh_tokens"  # type: ignore[assignment]

    token_id: UUID = Field(default_factory=_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.user_id", index=True)
    token_hash: str = Field(unique=True, max_length=64)
    expires_at: datetime
    revoked_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# User preferences
# ---------------------------------------------------------------------------


class UserPreference(SQLModel, table=True):
    """Per-user job-search preferences.

    One row per user (enforced by the unique constraint on ``user_id``).
    All list fields are stored as JSON arrays.  ``score_threshold``
    is the minimum weighted match score (0–100) before the platform
    suggests tailoring a resume for a job.
    """

    __tablename__ = "user_preferences"  # type: ignore[assignment]

    pref_id: UUID = Field(default_factory=_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.user_id", unique=True, index=True)
    target_roles: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    locations: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    remote_preference: str = Field(default="any", max_length=16)
    # CHECK: remote_preference IN ('remote', 'hybrid', 'onsite', 'any')
    employment_types: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    salary_min: Optional[int] = Field(default=None)
    salary_currency: str = Field(default="INR", max_length=8)
    work_authorization: str = Field(default="", max_length=128)
    notice_period_days: Optional[int] = Field(default=None)
    score_threshold: float = Field(default=35.0)
    preferred_sites: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    updated_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Candidate profile and evidence
# ---------------------------------------------------------------------------


class CandidateProfile(SQLModel, table=True):
    """Versioned candidate profile.

    ``profile_json`` holds the full ``Profile`` Pydantic model as JSONB
    so structured data is queryable without a separate column per field.
    ``is_active`` is true for the version currently used by the matching
    and resume engines; older versions are retained for traceability.
    ``source_file_ref`` is the private storage key for the original
    uploaded PDF or DOCX — never a public URL.
    """

    __tablename__ = "candidate_profiles"  # type: ignore[assignment]

    profile_id: UUID = Field(default_factory=_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.user_id", index=True)
    profile_version: int = Field(default=1)
    is_active: bool = Field(default=True)
    profile_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    source_file_ref: Optional[str] = Field(default=None, max_length=512)
    source_file_type: Optional[str] = Field(default=None, max_length=8)
    # CHECK: source_file_type IN ('pdf', 'docx', NULL)
    parse_status: str = Field(default="pending", max_length=16)
    # CHECK: parse_status IN ('pending', 'parsed', 'failed')
    created_at: datetime = Field(default_factory=_now)


class CandidateEvidence(SQLModel, table=True):
    """Single verifiable claim from the candidate's profile.

    This is the central integrity record.  Every bullet, skill, and
    qualification that the resume engine may use must have a row here
    with ``allowed_use = true``.

    ``source_reference`` is a human-readable pointer to where in the
    profile the claim originates, e.g. ``experience[0].bullets[2]`` or
    ``skills[5]``.

    ``source_text`` is the exact original text extracted from the upload
    — immutable after creation.

    ``job_requirements`` is a JSON array of ``req_id`` UUIDs populated
    by the matching engine when it determines which requirements this
    evidence supports.

    Status transitions (enforced in services/evidence.py):
      unverified  → verified       : sets allowed_use=true, verified_at=now()
      unverified  → user_approved  : sets allowed_use=true, verified_at=now()
      verified    → contradicted   : sets allowed_use=false
      contradicted: requires explicit re-verification before allowed_use=true
    """

    __tablename__ = "candidate_evidence"  # type: ignore[assignment]

    evidence_id: UUID = Field(default_factory=_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.user_id", index=True)
    profile_id: UUID = Field(foreign_key="candidate_profiles.profile_id", index=True)
    claim: str
    source_reference: str = Field(max_length=256)
    source_text: str
    verification_status: str = Field(default="unverified", max_length=16)
    # CHECK: verification_status IN ('unverified','verified','contradicted','user_approved')
    allowed_use: bool = Field(default=False)
    job_requirements: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=_now)
    verified_at: Optional[datetime] = Field(default=None)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


class Job(SQLModel, table=True):
    """Normalized, deduplicated job listing scoped to one user.

    ``raw_json`` preserves the full ``RawJob`` payload for provenance.
    ``external_id`` is the source board's own job identifier when
    available; the unique index on ``(user_id, source_name, external_id)``
    prevents duplicates within a source per user.

    ``status`` tracks whether the listing is still live:
      active | expired | closed | removed
    """

    __tablename__ = "jobs"  # type: ignore[assignment]

    job_id: UUID = Field(default_factory=_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.user_id", index=True)
    external_id: Optional[str] = Field(default=None, max_length=256)
    source_name: str = Field(max_length=64)
    company: str = Field(default="", max_length=256)
    title: str = Field(default="", max_length=256)
    location: str = Field(default="", max_length=256)
    employment_type: Optional[str] = Field(default=None, max_length=64)
    description_text: str = Field(default="")
    canonical_url: Optional[str] = Field(default=None, max_length=2048)
    apply_url: Optional[str] = Field(default=None, max_length=2048)
    posting_date: Optional[datetime] = Field(default=None)
    first_seen_at: datetime = Field(default_factory=_now)
    last_seen_at: datetime = Field(default_factory=_now)
    status: str = Field(default="active", max_length=16)
    # CHECK: status IN ('active', 'expired', 'closed', 'removed')
    raw_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))


class JobRequirement(SQLModel, table=True):
    """Single requirement extracted and classified from a job description.

    ``requirement_text`` is the original sentence/phrase from the JD.
    ``normalized_term`` is the canonical skill or qualification name
    used for matching against ``CandidateEvidence``.

    ``importance`` drives scoring:
      required     → counted in the 50% required-skill component
      preferred    → counted in the 10% preferred-skill component
      disqualifying → treated as a mandatory failure if candidate matches

    ``user_reclassified`` is set to true when the user manually overrides
    the extracted importance, so re-extraction doesn't clobber it.
    """

    __tablename__ = "job_requirements"  # type: ignore[assignment]

    req_id: UUID = Field(default_factory=_uuid, primary_key=True)
    job_id: UUID = Field(foreign_key="jobs.job_id", index=True)
    user_id: UUID = Field(foreign_key="users.user_id", index=True)
    requirement_text: str
    normalized_term: Optional[str] = Field(default=None, max_length=256)
    category: str = Field(default="skill", max_length=32)
    # CHECK: category IN ('skill','experience','education','location','work_auth','other')
    importance: str = Field(default="preferred", max_length=16)
    # CHECK: importance IN ('required','preferred','disqualifying')
    extracted_at: datetime = Field(default_factory=_now)
    user_reclassified: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


class JobMatch(SQLModel, table=True):
    """Explainable job-fit score for one user/job/profile combination.

    Component scores map to the agreed weighting:
      score_required_skills  : 50% weight
      score_experience       : 25% weight
      score_role_relevance   : 15% weight
      score_preferred_skills : 10% weight
      total_score            : weighted sum, 0–100

    ``mandatory_pass`` is stored separately from ``total_score`` so a
    candidate with a high keyword score but a failed work-authorization
    requirement is never misleadingly shown as "ready".

    ``explanation`` is a JSONB object keyed by ``req_id``, each value
    containing: requirement_text, importance, evidence_state, evidence_id,
    evidence_text.  See docs/platform-schema.md for the full shape.

    Scores are deterministic: the same job_id + profile_id +
    scoring_model_version always produces the same result.
    """

    __tablename__ = "job_matches"  # type: ignore[assignment]

    match_id: UUID = Field(default_factory=_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.user_id", index=True)
    job_id: UUID = Field(foreign_key="jobs.job_id")
    profile_id: UUID = Field(foreign_key="candidate_profiles.profile_id")
    scoring_model_version: str = Field(default="1.0", max_length=16)
    score_required_skills: Optional[float] = Field(default=None)
    score_experience: Optional[float] = Field(default=None)
    score_role_relevance: Optional[float] = Field(default=None)
    score_preferred_skills: Optional[float] = Field(default=None)
    total_score: Optional[float] = Field(default=None)
    mandatory_pass: Optional[bool] = Field(default=None)
    mandatory_failures: list[Any] = Field(default_factory=list, sa_column=Column(JSONB))
    explanation: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Resume versions and validation
# ---------------------------------------------------------------------------


class ResumeVersion(SQLModel, table=True):
    """A single tailored resume generated for one job.

    Lifecycle (Contract 2 enforced in services/resume_integrity.py):
      draft → generated → validating → validation_failed (loop)
                                     → ready_for_review   (all three gates pass)
      ready_for_review → user_approved_for_application
      user_approved_for_application → superseded | deleted

    ``resume_json`` holds the ``TailoredResume`` Pydantic model.
    ``file_ref`` is the private storage key for the generated PDF.

    A high ``total_score`` on the linked JobMatch does NOT automatically
    advance status — document validity and user review are independent.
    """

    __tablename__ = "resume_versions"  # type: ignore[assignment]

    resume_version_id: UUID = Field(default_factory=_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.user_id", index=True)
    job_id: UUID = Field(foreign_key="jobs.job_id")
    profile_id: UUID = Field(foreign_key="candidate_profiles.profile_id")
    match_id: Optional[UUID] = Field(default=None, foreign_key="job_matches.match_id")
    template_version: str = Field(default="1.0", max_length=16)
    status: str = Field(default="draft", max_length=40)
    # CHECK: status IN (
    #   'draft','generated','validating','validation_failed',
    #   'ready_for_review','user_approved_for_application',
    #   'superseded','deleted'
    # )
    resume_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    file_ref: Optional[str] = Field(default=None, max_length=512)
    created_at: datetime = Field(default_factory=_now)
    approved_at: Optional[datetime] = Field(default=None)


class ResumeValidation(SQLModel, table=True):
    """Result of the three-gate integrity check for one ResumeVersion.

    Gate (a) — pdf_extraction_ok:  re-extracted text matches the
               structured intermediate representation.
    Gate (b) — integrity_ok:       every claim traces to a
               CandidateEvidence row with allowed_use=true.
    Gate (c) — unsupported_claims: JSON array must be empty.

    All three must be true before ``ResumeVersion.status`` may advance
    to ``ready_for_review``.  Failing any gate holds status at
    ``validation_failed`` and populates the relevant fields for display.
    """

    __tablename__ = "resume_validations"  # type: ignore[assignment]

    validation_id: UUID = Field(default_factory=_uuid, primary_key=True)
    resume_version_id: UUID = Field(
        foreign_key="resume_versions.resume_version_id", index=True
    )
    user_id: UUID = Field(foreign_key="users.user_id", index=True)
    pdf_extraction_ok: bool = Field(default=False)
    integrity_ok: bool = Field(default=False)
    unsupported_claims: list[Any] = Field(default_factory=list, sa_column=Column(JSONB))
    keyword_coverage: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB)
    )
    layout_warnings: list[Any] = Field(default_factory=list, sa_column=Column(JSONB))
    overall_status: str = Field(default="pending", max_length=8)
    # CHECK: overall_status IN ('pending', 'pass', 'fail')
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Applications and approval (Contract 3)
# ---------------------------------------------------------------------------


class Application(SQLModel, table=True):
    """Stateful workflow record linking a user, job, and resume version.

    One application per user per job (unique constraint on user_id + job_id).
    Status progresses through the pipeline states; each transition is
    recorded as an ``ApplicationEvent``.

    Contract 3 — the status may only reach 'user_submitted' via the
    ``Approval`` table, never by opening the application URL alone.
    """

    __tablename__ = "applications"  # type: ignore[assignment]

    application_id: UUID = Field(default_factory=_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.user_id", index=True)
    job_id: UUID = Field(foreign_key="jobs.job_id")
    resume_version_id: Optional[UUID] = Field(
        default=None, foreign_key="resume_versions.resume_version_id"
    )
    status: str = Field(default="discovered", max_length=32)
    # CHECK: status IN (
    #   'discovered','normalized','matched','resume_generating',
    #   'resume_validating','resume_ready','pending_user_review',
    #   'application_prepared','pending_approval','user_submitted',
    #   'failed','expired','closed'
    # )
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ApplicationEvent(SQLModel, table=True):
    """Append-only audit trail for every application state change.

    ``event_type`` covers:
      status_changed | url_opened | user_confirmed_submission |
      resume_approved | error | retry

    ``url_opened`` is a deliberate separate event type — it never
    triggers a transition to ``user_submitted`` in the application layer.

    ``metadata_json`` may contain the from/to status, error message, or
    other context.  It must never contain resume content or credentials.
    """

    __tablename__ = "application_events"  # type: ignore[assignment]

    event_id: UUID = Field(default_factory=_uuid, primary_key=True)
    application_id: UUID = Field(
        foreign_key="applications.application_id", index=True
    )
    user_id: UUID = Field(foreign_key="users.user_id", index=True)
    event_type: str = Field(max_length=40)
    from_status: Optional[str] = Field(default=None, max_length=32)
    to_status: Optional[str] = Field(default=None, max_length=32)
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB)
    )
    created_at: datetime = Field(default_factory=_now)


class Approval(SQLModel, table=True):
    """Explicit per-application user approval record.

    Contract 3 fields — all four must be present before
    ``Application.status`` may transition to ``user_submitted``:

      1. application_id           — identifies the specific application
      2. approved_resume_version_id — the exact resume version approved
      3. approved_at              — non-null timestamp of the approval action
      4. user_confirmed_submission — must be explicitly set to True

    ``submitted_at`` and ``external_reference`` are populated only after
    the user confirms they actually submitted on the employer's site.

    Opening the application URL sets ``url_opened_at`` and creates an
    ``ApplicationEvent(event_type='url_opened')``; it does NOT set
    ``user_confirmed_submission`` or advance the application status.
    """

    __tablename__ = "approvals"  # type: ignore[assignment]

    approval_id: UUID = Field(default_factory=_uuid, primary_key=True)
    application_id: UUID = Field(
        foreign_key="applications.application_id", unique=True, index=True
    )
    user_id: UUID = Field(foreign_key="users.user_id", index=True)
    approved_resume_version_id: UUID = Field(
        foreign_key="resume_versions.resume_version_id"
    )
    user_confirmed_submission: bool = Field(default=False)
    approved_at: datetime = Field(default_factory=_now)
    url_opened_at: Optional[datetime] = Field(default=None)
    submitted_at: Optional[datetime] = Field(default=None)
    external_reference: Optional[str] = Field(default=None, max_length=512)


# ---------------------------------------------------------------------------
# Audit and data lifecycle
# ---------------------------------------------------------------------------


class AuditEvent(SQLModel, table=True):
    """Platform-level audit log for security-relevant actions.

    Log identifiers and action categories only — never passwords,
    tokens, resume content, or API keys.

    Covers: login | logout | file_upload | export_request |
            delete_account | password_reset | email_verified |
            evidence_verified | resume_approved | application_submitted
    """

    __tablename__ = "audit_events"  # type: ignore[assignment]

    event_id: UUID = Field(default_factory=_uuid, primary_key=True)
    user_id: Optional[UUID] = Field(
        default=None, foreign_key="users.user_id", index=True
    )
    action: str = Field(max_length=64)
    resource_type: Optional[str] = Field(default=None, max_length=64)
    resource_id: Optional[str] = Field(default=None, max_length=64)
    ip_address: Optional[str] = Field(default=None, max_length=45)
    created_at: datetime = Field(default_factory=_now)


class ExportRequest(SQLModel, table=True):
    """User-initiated full-data export request.

    ``file_ref`` is the private storage key for the generated zip archive;
    it is null until the export job completes.  ``expires_at`` is set when
    the file is ready; after expiry the file is deleted and ``status``
    transitions to ``expired``.
    """

    __tablename__ = "export_requests"  # type: ignore[assignment]

    request_id: UUID = Field(default_factory=_uuid, primary_key=True)
    user_id: UUID = Field(foreign_key="users.user_id", index=True)
    status: str = Field(default="pending", max_length=16)
    # CHECK: status IN ('pending', 'ready', 'expired', 'failed')
    file_ref: Optional[str] = Field(default=None, max_length=512)
    expires_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    completed_at: Optional[datetime] = Field(default=None)
