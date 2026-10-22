"""Cover letter agent — structured CoverLetter sections."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from jobapply.agents._structured import invoke_structured
from jobapply.models import CoverLetter, RawJob, TailoredResume


def write_cover_letter(
    llm: BaseChatModel,
    *,
    profile_text: str,
    job: RawJob,
    resume: TailoredResume,
) -> CoverLetter:
    jd = (job.description or "")[:10000]
    sys = SystemMessage(
        content=(
            "You are a skilled professional writer helping someone apply for a job. "
            "Write a cover letter that sounds natural, warm, and genuinely excited — "
            "like a real person talking to another person, not a template.\n\n"
            "CRITICAL RULES:\n"
            "- Write like a human, not an AI. Be conversational but professional.\n"
            "- NEVER use these phrases: 'I am writing to express', 'I am excited to apply', "
            "'I came across', 'I believe I would be', 'I am confident', 'strong candidate'\n"
            "- Start with something specific about the company or role that genuinely interests you\n"
            "- Use short, punchy sentences mixed with longer ones. Vary your rhythm.\n"
            "- Show personality — let the candidate's actual experience and voice come through\n"
            "- Be specific about what you've actually done, not generic claims\n"
            "- Skip the corporate jargon. Write like you're talking to a friend who works there.\n\n"
            "Output a SINGLE JSON object with exactly four string fields:\n"
            "- `header`: candidate's name, email, phone, date, company name (plain text, newline-separated)\n"
            "- `opening`: A natural greeting + one compelling sentence about why this role\n"
            "- `body`: 2-3 short paragraphs with specific examples from their experience that match the role\n"
            "- `closing`: A warm, confident close + signature (avoid 'I look forward to hearing from you')\n\n"
            "Make it sound like someone who actually wants this job and knows what they're talking about."
        ),
    )
    user = HumanMessage(
        content=(
            f"JOB: {job.title} at {job.company}\nURL: {job.job_url or job.apply_url or ''}\n\n"
            f"JD:\n{jd}\n\n"
            f"PROFILE:\n{profile_text[:8000]}\n\n"
            f"TAILORED RESUME SUMMARY:\n{resume.summary}\n"
            f"TOP SKILLS: {', '.join(resume.skills[:25])}"
        ),
    )
    return invoke_structured(llm, CoverLetter, [sys, user])
