# jobapply Platform — Database Schema & Setup Guide

This document covers the multi-user PostgreSQL schema, the three
integrity contracts enforced in application code, how to run the
initial migration, and how to verify the setup.

---

## Overview

The existing CLI uses three local SQLite files:

| File | Purpose | Managed by |
|---|---|---|
| `.jobapply/ledger.db` | Cross-run deduplication | `jobapply.ledger` (SQLModel) |
| `<workspace>/workspace.db` | Job catalog per workspace | `jobapply.workspace` (SQLModel) |
| `<run>/checkpoint.sqlite` | LangGraph graph state | LangGraph |

These are **not touched by Alembic**. They continue to work for all CLI
commands (`jobapply run`, `jobapply search`, `jobapply tailor`).

The new PostgreSQL schema powers the multi-user web platform only. It
is managed exclusively by Alembic. Never call
`SQLModel.metadata.create_all()` against the PostgreSQL database.

---

## Tables

### Authentication

| Table | Purpose |
|---|---|
| `users` | Registered accounts. `password_hash` is bcrypt/argon2; plaintext is never stored. `email_verified_at` is null until verified. |
| `email_tokens` | Single-use, expiring tokens for email verification and password reset. `token_hash` stores the SHA-256 digest; the raw token is sent to the user and never persisted. |
| `refresh_tokens` | Stored refresh tokens for JWT rotation. Enables server-side revocation on logout or account suspension. |

### User configuration

| Table | Purpose |
|---|---|
| `user_preferences` | One row per user. Target roles, locations, remote preference, salary, work authorization, notice period, score threshold, preferred job sites. |

### Candidate profile and evidence

| Table | Purpose |
|---|---|
| `candidate_profiles` | Versioned profile. `profile_json` holds the full `Profile` Pydantic model as JSONB. `source_file_ref` is a private storage key — never a public URL. |
| `candidate_evidence` | The central integrity record. One row per verifiable claim (bullet, skill, qualification). See Contract 1. |

### Jobs

| Table | Purpose |
|---|---|
| `jobs` | Normalized, deduplicated, user-scoped job listing. `raw_json` preserves the full `RawJob` for provenance. |
| `job_requirements` | Extracted and classified requirements per job. `importance`: required / preferred / disqualifying. |

### Matching

| Table | Purpose |
|---|---|
| `job_matches` | Explainable weighted score. Component scores (50/25/15/10 weights) stored separately from mandatory check result. `explanation` JSONB contains per-requirement evidence states. |

### Resume

| Table | Purpose |
|---|---|
| `resume_versions` | One tailored resume per job. Lifecycle tracked via `status`. `file_ref` is a private storage key. See Contract 2. |
| `resume_validations` | Result of the three-gate integrity check. All three gates must pass before status advances to `ready_for_review`. |

### Applications

| Table | Purpose |
|---|---|
| `applications` | Stateful workflow record. One per user per job (unique constraint). |
| `application_events` | Append-only audit trail for every state change. `url_opened` is a distinct event type that never triggers submission. |
| `approvals` | Explicit per-application approval record. See Contract 3. |

### Lifecycle and audit

| Table | Purpose |
|---|---|
| `audit_events` | Platform-level security log. IDs and action categories only — never passwords, tokens, or resume content. |
| `export_requests` | User-initiated full data export. `file_ref` populated when ready; expires and is deleted on schedule. |

---

## The Three Integrity Contracts

These contracts are documented in `jobapply/db/models.py` and enforced in
the application service layer (`jobapply/services/`). Contract 1 also has
a DB-level `CHECK` constraint as a safety net.

### Contract 1 — Evidence eligibility

A `JobRequirement` may only be scored `SUPPORTED` when at least one
`CandidateEvidence` row matches it with:

```
verification_status IN ('verified', 'user_approved')
AND allowed_use = true
```

Any other state produces: `UNVERIFIED`, `NO_EVIDENCE`, `CONFIRMED_GAP`,
or `MANDATORY_FAILURE`. Unverified records do not contribute a positive
score.

DB enforcement: `ck_evidence_allowed_use_consistent` CHECK constraint on
`candidate_evidence` ensures `allowed_use = true` is only possible when
`verification_status` is `verified` or `user_approved`.

### Contract 2 — Resume readiness

A `ResumeVersion` may only transition to `ready_for_review` when ALL of:

```
(a) pdf_extraction_ok = true       (re-extracted text matches intent)
(b) integrity_ok = true            (every claim traces to allowed evidence)
(c) unsupported_claims = []        (no unsupported claims found)
```

A high `total_score` on the linked `JobMatch` does NOT automatically
advance status. Document validity and user review are independent gates.
Failing any condition holds status at `validation_failed` and populates
the relevant `ResumeValidation` fields for display.

### Contract 3 — Application submission

`Application.status` may only transition to `user_submitted` when the
linked `Approval` row has ALL of:

```
1. application_id                  — identifies the specific application
2. approved_resume_version_id      — the exact resume version the user approved
3. approved_at IS NOT NULL         — timestamp of the approval action
4. user_confirmed_submission = true — explicit user action, not inferred
```

`url_opened_at` records when the user opened the employer's application
page. It creates an `ApplicationEvent(event_type='url_opened')` and
**does not** set `user_confirmed_submission` or advance `Application.status`.

---

## Evidence status transitions

```
unverified  →  verified       sets allowed_use=true,  verified_at=now()
unverified  →  user_approved  sets allowed_use=true,  verified_at=now()
verified    →  contradicted   sets allowed_use=false
contradicted   requires explicit re-verification before allowed_use=true
```

Enforced in: `jobapply/services/evidence.py` (to be created in Stage 1, Step 3).

---

## Resume version lifecycle

```
draft
  → generated
  → validating
      → validation_failed   ← fix and regenerate
      → ready_for_review    ← all three gates pass
          → user_approved_for_application
              → superseded  (newer version approved)
              → deleted
```

---

## Application status pipeline

```
discovered → normalized → matched → resume_generating → resume_validating
  → resume_ready → pending_user_review → application_prepared
  → pending_approval → user_submitted

FAILED    (at any stage; stores error + recovery action)
EXPIRED   (job no longer available)
CLOSED    (user closed the application)
```

---

## JobMatch explanation JSON shape

`job_matches.explanation` is a JSONB object keyed by `req_id` (UUID string):

```json
{
  "3fa85f64-5717-4562-b3fc-2c963f66afa6": {
    "requirement_text": "5+ years Python",
    "importance": "required",
    "evidence_state": "SUPPORTED",
    "evidence_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "evidence_text": "4 years Python at Acme Corp building data pipelines"
  },
  "6ba7b810-9dad-11d1-80b4-00c04fd430c8": {
    "requirement_text": "Kubernetes experience",
    "importance": "preferred",
    "evidence_state": "NO_EVIDENCE",
    "evidence_id": null,
    "evidence_text": null
  }
}
```

Valid `evidence_state` values: `SUPPORTED`, `UNVERIFIED`, `NO_EVIDENCE`,
`CONFIRMED_GAP`, `MANDATORY_FAILURE`.

---

## Setup instructions

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ (a dedicated database for jobapply)
- The repo installed in a virtual environment

### 1. Install dependencies

```bash
# Using uv (recommended — matches existing uv.lock workflow)
uv pip install -e ".[dev]"

# Or standard pip
pip install -e ".[dev]"
```

The new dependencies added to `pyproject.toml`:

| Package | Purpose |
|---|---|
| `alembic>=1.13.0` | Migration management |
| `psycopg[binary]>=3.1.0` | PostgreSQL async driver (psycopg3) |
| `passlib[bcrypt]>=1.7.4` | Password hashing |
| `python-jose[cryptography]>=3.3.0` | JWT signing and verification |
| `slowapi>=0.1.9` | FastAPI rate limiting |

### 2. Create a dedicated PostgreSQL database

```sql
-- Run as a PostgreSQL superuser
CREATE USER jobapply WITH PASSWORD 'changeme';
CREATE DATABASE jobapply OWNER jobapply;
```

Use a disposable database for first-run testing. Never use the same
database as another application.

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL and SECRET_KEY at minimum:
#   DATABASE_URL=postgresql+psycopg://jobapply:changeme@localhost:5432/jobapply
#   SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

### 4. Run the migration

```bash
export DATABASE_URL="postgresql+psycopg://jobapply:changeme@localhost:5432/jobapply"

# Apply all migrations
alembic upgrade head

# Confirm current revision
alembic current
# Expected: 0001 (head)
```

### 5. Verify the schema

```bash
# List all created tables
psql -U jobapply -d jobapply -c "\dt"
```

Expected output (16 tables):

```
 Schema |        Name         | Type  |  Owner
--------+---------------------+-------+---------
 public | application_events  | table | jobapply
 public | applications        | table | jobapply
 public | approvals           | table | jobapply
 public | audit_events        | table | jobapply
 public | candidate_evidence  | table | jobapply
 public | candidate_profiles  | table | jobapply
 public | email_tokens        | table | jobapply
 public | export_requests     | table | jobapply
 public | job_matches         | table | jobapply
 public | job_requirements    | table | jobapply
 public | jobs                | table | jobapply
 public | refresh_tokens      | table | jobapply
 public | resume_validations  | table | jobapply
 public | resume_versions     | table | jobapply
 public | user_preferences    | table | jobapply
 public | users               | table | jobapply
```

Plus the `alembic_version` table managed by Alembic itself.

### 6. Verify the downgrade (optional but recommended)

```bash
# Roll back everything
alembic downgrade base

# Confirm no platform tables remain
psql -U jobapply -d jobapply -c "\dt"
# Expected: only alembic_version

# Re-apply
alembic upgrade head
```

---

## Generating future migrations

After changing `jobapply/db/models.py`:

```bash
# Auto-detect schema drift and generate a new migration
alembic revision --autogenerate -m "describe the change"

# Review the generated file in alembic/versions/ before applying
alembic upgrade head
```

Always review autogenerated migrations before applying them. Alembic
can miss some changes (e.g. CHECK constraints, partial indexes) and may
generate drop/recreate statements that need manual adjustment.

---

## What comes next (Stage 1, Steps 2–5)

| Step | Work |
|---|---|
| Step 2 | `jobapply/auth/` — registration, email verification, login, JWT issue/refresh/revoke, rate limiting, `get_current_user` dependency |
| Step 3 | `jobapply/services/evidence.py` — `CandidateEvidence` CRUD, status transition rules, `profile_to_evidence_records()` |
| Step 4 | `jobapply/services/matching.py` — explainable 50/25/15/10 weighted score replacing `fit_scorer.py`; `jobapply/services/resume_integrity.py` — PDF re-extraction + three-gate validation |
| Step 5 | `jobapply/services/application.py` — application state machine + Contract 3 enforcement |

No existing CLI code changes until Step 3, when `resume_tailor.py` gains
an evidence-record pre-filter.

---

## Security notes

- Never log `password_hash`, `token_hash`, resume content, or API keys.
- `audit_events` logs action names and resource IDs only.
- All file references (`source_file_ref`, `file_ref`) are private storage
  keys — never public URLs. Signed, time-limited URLs are generated on
  demand by the file-serving routes.
- Cross-user access: every query on a user-owned table must include
  `WHERE user_id = :current_user_id`. Return 404 (not 403) for
  cross-user access attempts so existence is not leaked.
- `email_tokens.used_at` must be set atomically in the same transaction
  that processes the token. Read-then-write across two transactions
  creates a race condition.
