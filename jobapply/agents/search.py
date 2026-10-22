"""JobSpy search with retries."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

from tenacity import retry, stop_after_attempt, wait_exponential

from jobapply.jd_extract import extract_application_hints
from jobapply.models import JobSearchInput, RawJob
from jobapply.utils import stable_job_id
import re


def _row_to_dict(row: Any) -> dict[str, Any]:
    if hasattr(row, "to_dict"):
        return dict(row.to_dict())
    if isinstance(row, dict):
        return dict(row)
    return dict(row._asdict()) if hasattr(row, "_asdict") else dict(row)


def _matches_experience_level(description: str, title: str, level: str) -> bool:
    """Check if job matches the experience level filter - STRICT matching."""
    if not level or not description:
        return True
    
    text = (description + " " + title).lower()
    
    # STRICT patterns - must match at least one pattern
    patterns = {
        "internship": [
            r"\bintern\b", r"\binternship\b", r"\bstudent\b",
            r"\bgraduate program\b", r"\bcampus\b", r"\btrainee\b"
        ],
        "entry": [
            r"\bentry.level\b", r"\bjunior\b", r"\b0.2 year", r"\b0.1 year",
            r"\b1.2 year", r"\bfresh graduate\b", r"\bnewly graduated\b",
            r"\bno experience required\b", r"\bearly career\b"
        ],
        "mid": [
            r"\bmid.level\b", r"\b2.5 year", r"\b3.5 year", r"\b4.5 year",
            r"\b3.4 year", r"\bintermediate\b", r"\bexperienced\b"
        ],
        "senior": [
            r"\bsenior\b", r"\bsr\.", r"\b5\+ year", r"\b6\+ year", r"\b7\+ year",
            r"\b8\+ year", r"\bexpert\b", r"\badvanced\b", r"\b5-\d+ year"
        ],
        "lead": [
            r"\blead\b", r"\bstaff\b", r"\bprincipal\b", r"\barchitect\b",
            r"\bmanager\b", r"\bhead of\b", r"\bdirector\b", r"\bsenior staff\b"
        ],
    }
    
    # STRICT exclusion patterns - if found, REJECT the job
    exclusions = {
        "internship": [
            r"\b3\+ year", r"\b4\+ year", r"\b5\+ year", r"\bsenior\b",
            r"\blead\b", r"\bmanager\b", r"\bmid.level\b"
        ],
        "entry": [
            r"\b5\+ year", r"\b6\+ year", r"\bsenior\b", r"\blead\b",
            r"\bstaff\b", r"\b4\+ year"
        ],
        "mid": [
            r"\bintern\b", r"\binternship\b", r"\b7\+ year", r"\b8\+ year",
            r"\bsenior\b", r"\blead\b", r"\bstaff\b", r"\bprincipal\b"
        ],
        "senior": [
            r"\bintern\b", r"\binternship\b", r"\bjunior\b",
            r"\bentry.level\b", r"\b0.2 year", r"\b1.2 year"
        ],
        "lead": [
            r"\bintern\b", r"\binternship\b", r"\bjunior\b",
            r"\bentry.level\b", r"\b0.2 year", r"\b1.3 year"
        ],
    }
    
    # Check EXCLUSIONS first - if any exclusion matches, REJECT
    for exclusion in exclusions.get(level, []):
        if re.search(exclusion, text):
            return False
    
    # Check if job matches any REQUIRED pattern
    for pattern in patterns.get(level, []):
        if re.search(pattern, text):
            return True
    
    # No pattern matched - REJECT
    return False


def _matches_job_type(description: str, title: str, job_type: str | list[str]) -> bool:
    """Check if job matches the job type filter - STRICT matching.
    
    If job_type is a list, returns True if ANY of the types match (OR logic).
    """
    if not job_type or not description:
        return True
    
    # Handle list of job types - return True if ANY match
    if isinstance(job_type, list):
        return any(_matches_single_job_type(description, title, jt) for jt in job_type)
    
    return _matches_single_job_type(description, title, job_type)


def _matches_single_job_type(description: str, title: str, job_type: str) -> bool:
    """Check if job matches a single job type filter - STRICT matching."""
    if not job_type or not description:
        return True
    
    text = (description + " " + title).lower()
    
    # STRICT patterns - must explicitly mention the type
    patterns = {
        "fulltime": [
            r"\bfull.time\b", r"\bfull time\b", r"\bpermanent\b", 
            r"\bfte\b", r"\bfull-time\b", r"\bfull\s+time\b"
        ],
        "parttime": [
            r"\bpart.time\b", r"\bpart time\b", r"\bpart-time\b", r"\bpart\s+time\b"
        ],
        "contract": [
            r"\bcontract\b", r"\bcontractor\b", r"\bc2c\b", r"\bc2h\b",
            r"\bcontract to hire\b", r"\bfixed.term\b", r"\btemporary\b"
        ],
        "freelance": [
            r"\bfreelance\b", r"\bfreelancer\b", r"\bgig\b", 
            r"\bindependent contractor\b", r"\bconsultant\b"
        ],
        "internship_type": [
            r"\bintern\b", r"\binternship\b", r"\bco-op\b", r"\btrainee\b"
        ],
    }
    
    # Exclusions - reject if found
    exclusions = {
        "fulltime": [
            r"\bpart.time\b", r"\bpart-time\b", r"\bcontract\b",
            r"\bfreelance\b", r"\bc2c\b", r"\bc2h\b"
        ],
        "parttime": [
            r"\bfull.time\b", r"\bfull-time\b", r"\bpermanent\b"
        ],
        "contract": [
            r"\bfull.time permanent\b", r"\bpermanent full.time\b"
        ],
        "freelance": [
            r"\bfull.time\b", r"\bfte\b", r"\bpermanent\b"
        ],
        "internship_type": [
            r"\bfull.time\b", r"\bpermanent\b", r"\b3\+ year", r"\b5\+ year"
        ],
    }
    
    # Check exclusions first
    for exclusion in exclusions.get(job_type, []):
        if re.search(exclusion, text):
            return False
    
    # Check if matches required patterns
    for pattern in patterns.get(job_type, []):
        if re.search(pattern, text):
            return True
    
    # For fulltime, if nothing else matches, be lenient (assume fulltime)
    if job_type == "fulltime":
        # Only reject if explicitly mentions other types
        return True
    
    # No pattern matched - REJECT
    return False


@retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3))
def _scrape_once(
    *,
    site_name: list[str],
    search_term: str,
    location: str | None,
    results_wanted: int,
    hours_old: int,
    is_remote: bool,
    linkedin_fetch_description: bool = True,
) -> list[dict[str, Any]]:
    from jobspy import scrape_jobs

    # ``linkedin_fetch_description`` makes JobSpy issue an extra GET per
    # LinkedIn hit to scrape the full JD off the public job-view page.
    # JobSpy defaults this to False (fast, but `description` is blank
    # for every LinkedIn row), which silently breaks `jobapply tailor`
    # later — so we default to True and let the caller opt out.
    raw = scrape_jobs(
        site_name=site_name,
        search_term=search_term,
        location=location or "",
        results_wanted=results_wanted,
        hours_old=hours_old,
        is_remote=is_remote,
        linkedin_fetch_description=linkedin_fetch_description,
    )
    if hasattr(raw, "to_dict"):
        records = raw.to_dict("records")
        return cast(list[dict[str, Any]], records)
    return cast(list[dict[str, Any]], list(raw))


def iter_search_jobs(inp: JobSearchInput) -> Iterator[RawJob]:
    """Stream JobSpy hits as they arrive, deduped by stable job_id.

    Yields one :class:`RawJob` at a time in title-major order so callers
    can persist results incrementally (e.g. ``jobapply search`` flushes
    ``jobs.json``/``jobs.csv`` after each yielded job for live feedback
    instead of waiting for the whole batch to finish). The generator
    stops as soon as ``inp.results_wanted`` unique jobs have been
    yielded.
    """
    site_name = inp.site_names or ["indeed", "linkedin", "google"]
    skills_q = " ".join(inp.skills) if inp.skills else ""
    seen: set[str] = set()
    yielded = 0
    # Request MORE results from JobSpy if we're filtering, since filters will reject many
    # Reduced multiplier from 5 to 2 for faster results
    # ULTRA FAST: No multiplier even with filters - get exactly what user asked for
    # This makes searches 2x faster when using experience level or job type filters
    multiplier = 1  # Removed filter multiplier for maximum speed
    per_title = max(5, min(inp.results_wanted * multiplier, 300 // max(1, len(inp.titles))))

    for title in inp.titles:
        term = f"{title.strip()} {skills_q}".strip()
        rows = _scrape_once(
            site_name=site_name,
            search_term=term,
            location=inp.location,
            results_wanted=per_title,
            hours_old=inp.hours_old,
            is_remote=inp.remote,
            linkedin_fetch_description=inp.linkedin_fetch_description,
        )
        for row in rows:
            d = _row_to_dict(row)
            title_s = str(d.get("title") or "")
            company = str(d.get("company") or "")
            location_s = str(d.get("location") or "")
            site = str(d.get("site") or "")
            job_url = d.get("job_url") or d.get("url")
            apply_url = d.get("job_url_apply") or d.get("apply_url") or job_url
            description = str(d.get("description") or "")
            
            # Apply experience level filter
            if inp.experience_level and not _matches_experience_level(
                description, title_s, inp.experience_level
            ):
                continue
            
            # Apply job type filter
            if inp.job_type and not _matches_job_type(
                description, title_s, inp.job_type
            ):
                continue
            
            jid = stable_job_id(
                site=site,
                company=company,
                title=title_s,
                location=location_s,
                apply_url=str(apply_url) if apply_url else None,
                job_url=str(job_url) if job_url else None,
            )
            if jid in seen:
                continue
            seen.add(jid)
            # Pull recipient email + subject-line / instruction hints
            # out of the JD body so downstream `--with-email` can
            # pre-fill `--email-to` / `--email-context` instead of
            # making the user copy-paste from the description.
            hints = extract_application_hints(description)
            yield RawJob(
                job_id=jid,
                title=title_s,
                company=company,
                location=location_s,
                description=description,
                job_url=str(job_url) if job_url else None,
                apply_url=str(apply_url) if apply_url else None,
                site=site,
                date_posted=str(d.get("date")) if d.get("date") else None,
                application=hints if hints.has_any else None,
                raw=d,
            )
            yielded += 1
            if yielded >= inp.results_wanted:
                return


def search_jobs(inp: JobSearchInput) -> list[RawJob]:
    """Run JobSpy for each title; merge and dedupe by stable job_id.

    Thin wrapper around :func:`iter_search_jobs` that materializes the
    full list upfront. Use the generator directly when you want to
    react to results as they arrive.
    """
    return list(iter_search_jobs(inp))
