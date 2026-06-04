"""Mock tools for the permission-gated recruiting CRM case study."""

from collections.abc import Sequence

from wayfinder.enterprise.state import CandidateProfile, Contact, JobDescription, JobMatch


def find_candidate(candidates: Sequence[CandidateProfile], candidate_id: str) -> CandidateProfile:
    """Return a candidate from synthetic local data."""
    for candidate in candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    raise KeyError(f"candidate not found: {candidate_id}")


def match_jobs_to_candidate(
    candidate: CandidateProfile,
    jobs: Sequence[JobDescription],
    *,
    limit: int = 3,
) -> list[JobMatch]:
    """Score jobs by requirement overlap against candidate skills and experience."""
    candidate_terms = _normalize_terms(
        [*candidate.skills, *candidate.experience, *candidate.target_roles]
    )
    matches: list[JobMatch] = []

    for job in jobs:
        requirements = _normalize_terms(job.requirements)
        nice_to_have = _normalize_terms(job.nice_to_have)
        matched_requirements = sorted(candidate_terms.intersection(requirements))
        matched_nice_to_have = sorted(candidate_terms.intersection(nice_to_have))
        denominator = max(len(requirements), 1)
        score = min(
            1.0,
            (len(matched_requirements) + (0.5 * len(matched_nice_to_have))) / denominator,
        )
        if score <= 0:
            continue
        reason = (
            f"Matched {len(matched_requirements)} required terms"
            f" and {len(matched_nice_to_have)} nice-to-have terms."
        )
        matches.append(
            JobMatch(
                job_id=job.job_id,
                company=job.company,
                title=job.title,
                score=round(score, 2),
                matched_requirements=matched_requirements,
                reason=reason,
            )
        )

    return sorted(matches, key=lambda match: (-match.score, match.company, match.title))[:limit]


def find_contact_for_company(contacts: Sequence[Contact], company: str) -> Contact | None:
    """Find a verified synthetic contact for a company."""
    for contact in contacts:
        if contact.company.lower() == company.lower():
            return contact
    return None


def draft_outreach(
    candidate: CandidateProfile,
    job_match: JobMatch,
    contact: Contact | None,
) -> str:
    """Create a draft-only outreach message."""
    if contact is None:
        return (
            f"No verified contact exists for {job_match.company}; do not send outreach until a "
            "real contact is selected."
        )

    skill_summary = ", ".join(candidate.skills[:4]) or "relevant project experience"
    return (
        f"Hi {contact.role}, I am preparing a referral request for {candidate.name} "
        f"for {job_match.company}'s {job_match.title} role. The strongest fit signals are "
        f"{skill_summary}. Could you review this draft before any outreach is sent?"
    )


def _normalize_terms(values: Sequence[str]) -> set[str]:
    terms: set[str] = set()
    for value in values:
        lowered = value.lower().replace("/", " ").replace("-", " ")
        terms.update(part for part in lowered.split() if part)
        if lowered.strip():
            terms.add(lowered.strip())
    return terms
