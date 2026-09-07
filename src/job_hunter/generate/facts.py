"""The profile as a prompt block.

The mirror of `Job.brief()`: one canonical way the user's facts enter a prompt,
so a change to how they are presented happens in one place. Roles and projects
are numbered because generators refer to them by index - the model never gets
to spell an employer's name, so it can never misspell or invent one.
"""

from __future__ import annotations

from ..profile.models import Profile


def profile_block(profile: Profile) -> str:
    """Everything in the profile, numbered where a generator must point at it."""
    parts: list[str] = []
    p = profile.personal

    if p.full_name:
        parts.append(f"Name: {p.full_name}")
    if p.headline:
        parts.append(f"Headline: {p.headline}")
    if place := ", ".join(x for x in (p.city, p.country) if x):
        parts.append(f"Based in: {place}")
    if profile.summary:
        parts.append(f"Current summary: {profile.summary}")
    if profile.skills:
        parts.append(f"Skills: {', '.join(profile.skills)}")

    if profile.experience:
        parts.append("\nExperience (refer to these by index):")
        for i, role in enumerate(profile.experience):
            head = " - ".join(x for x in (role.position, role.company) if x) or "Role"
            meta = ", ".join(x for x in (role.period, role.location, role.industry) if x)
            parts.append(f"[{i}] {head}" + (f" ({meta})" if meta else ""))
            parts.extend(f"      - {bullet}" for bullet in role.bullets)
            if role.skills:
                parts.append(f"      skills: {', '.join(role.skills)}")

    if profile.education:
        parts.append("\nEducation:")
        for edu in profile.education:
            head = " - ".join(x for x in (edu.level, edu.field_of_study, edu.institution) if x)
            meta = ", ".join(x for x in (edu.period, edu.grade) if x)
            parts.append(f"- {head}" + (f" ({meta})" if meta else ""))
            if edu.courses:
                parts.append(f"      courses: {', '.join(edu.courses)}")

    if profile.projects:
        parts.append("\nProjects (refer to these by index):")
        for i, project in enumerate(profile.projects):
            line = f"[{i}] {project.name}"
            if project.description:
                line += f" - {project.description}"
            if project.tech:
                line += f" (tech: {', '.join(project.tech)})"
            parts.append(line)

    if profile.certifications:
        certs = "; ".join(
            " ".join(x for x in (c.name, c.issuer, c.year) if x) for c in profile.certifications
        )
        parts.append(f"\nCertifications: {certs}")
    if profile.languages:
        langs = ", ".join(
            f"{lang.name} ({lang.level})" if lang.level else lang.name
            for lang in profile.languages
        )
        parts.append(f"Languages: {langs}")

    return "\n".join(parts).strip()
