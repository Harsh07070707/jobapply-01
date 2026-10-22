"""Referral detection for job descriptions.

Scans job descriptions for referral-related keywords and generates
referral request message templates.
"""

from __future__ import annotations

import re


REFERRAL_KEYWORDS = [
    r"\breferral\b",
    r"\bemployee referral\b",
    r"\breferral bonus\b",
    r"\breferral program\b",
    r"\breferred by\b",
    r"\binternal referral\b",
    r"\brefer someone\b",
    r"\bknow someone\b",
]


def detect_referral(description: str) -> bool:
    """Check if job description mentions referrals.
    
    Args:
        description: Job description text
        
    Returns:
        True if referral-related keywords found
    """
    if not description:
        return False
    
    desc_lower = description.lower()
    for pattern in REFERRAL_KEYWORDS:
        if re.search(pattern, desc_lower):
            return True
    return False


def generate_referral_message(
    job_title: str,
    company: str,
    candidate_name: str = "Your Name",
) -> str:
    """Generate a template message for requesting a referral.
    
    Args:
        job_title: Position title
        company: Company name
        candidate_name: Candidate's name (defaults to placeholder)
        
    Returns:
        Formatted referral request message
    """
    return f"""Hi [Employee Name],

I hope this message finds you well. I noticed that {company} is hiring for a {job_title} position, and I'm very interested in applying. I saw that the company has a referral program, and I was wondering if you'd be comfortable referring me for this role.

A bit about my background: [Add 2-3 sentences about your relevant experience, skills, and what makes you a strong fit for the role]

I've attached my resume for your review. If you feel comfortable referring me, I'd really appreciate it. If not, no worries at all – I completely understand.

Thank you for considering, and I hope we can connect soon!

Best regards,
{candidate_name}"""
