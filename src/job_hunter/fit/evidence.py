"""Finding what in a profile backs a requirement, and saying where.

The rule this package exists to keep: **evidence is looked for in the profile
and nowhere else.** A tailored CV can put a fact in front of a reader or bury
it, but it cannot create one, so a word copied out of the posting finds nothing
here. That is what makes measuring fit after tailoring worth anything.

`guard.Support.of(job)` must never appear in this module. A posting asking for
Kafka does not license claiming it - the same rule the invention guard keeps,
for the same reason.
"""

from __future__ import annotations

import re

from ..generate.guard import Support, norm
from ..profile.models import Profile
from .models import ASSERTED, CLAIMED, CREDENTIALED, DEMONSTRATED, Evidence


def skills_index(profile: Profile) -> list[str]:
    """Every skill the profile claims, deduplicated, longest first.

    Longest first so "Google Cloud" is reported rather than "Google" when both
    would match the same words. Ported from the search scorer this replaces.
    """
    named = list(profile.skills)
    for role in profile.experience:
        named.extend(role.skills)
    for project in profile.projects:
        named.extend(project.tech)
    seen: dict[str, str] = {}
    for skill in named:
        if (key := skill.strip().lower()) and key not in seen:
            seen[key] = skill.strip()
    return sorted(seen.values(), key=len, reverse=True)


def _mentions(term: str, text: str) -> bool:
    """Whether `text` names `term` as a word, not as a fragment.

    The boundary is what stops "Go" matching "going" and "Java" matching
    "JavaScript".
    """
    if not term.strip() or not text:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])",
                     text.lower()) is not None


def _quote(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _places(profile: Profile) -> list[tuple[str, str, str]]:
    """Every (path, kind, text) in the profile that could back a claim.

    In strength order, because where a claim is backed matters to whoever reads
    it: a sentence describing doing the thing beats the same word sitting in a
    comma-separated list.
    """
    places: list[tuple[str, str, str]] = []

    for i, role in enumerate(profile.experience):
        for j, bullet in enumerate(role.bullets):
            places.append((f"experience[{i}].bullets[{j}]", DEMONSTRATED, bullet))

    for i, education in enumerate(profile.education):
        for j, course in enumerate(education.courses):
            places.append((f"education[{i}].courses[{j}]", CREDENTIALED, course))
        places.append((f"education[{i}]", CREDENTIALED,
                       f"{education.level} {education.field_of_study} {education.institution}"))
    for i, cert in enumerate(profile.certifications):
        places.append((f"certifications[{i}]", CREDENTIALED,
                       f"{cert.name} {cert.issuer} {cert.description}"))
    for i, language in enumerate(profile.languages):
        places.append((f"languages[{i}]", CREDENTIALED,
                       f"{language.name} {language.level}"))

    for i, role in enumerate(profile.experience):
        for j, skill in enumerate(role.skills):
            places.append((f"experience[{i}].skills[{j}]", CLAIMED, skill))
        places.append((f"experience[{i}]", CLAIMED, f"{role.position} {role.industry}"))
    for i, project in enumerate(profile.projects):
        places.append((f"projects[{i}]", CLAIMED,
                       f"{project.name} {project.description} {' '.join(project.tech)}"))
    for i, skill in enumerate(profile.skills):
        places.append((f"skills[{i}]", CLAIMED, skill))

    places.append(("summary", ASSERTED, profile.summary))
    places.append(("personal.headline", ASSERTED, profile.personal.headline))
    return places


def find(term: str, profile: Profile, *, support: Support | None = None) -> list[Evidence]:
    """Every place in the profile that backs `term`, strongest first.

    `support` is an optional pre-built `Support.of(profile)`, used only to skip
    the search for a word the profile does not contain at all. It is a filter,
    never the answer: a bag of words cannot say *where* a claim is backed, and a
    number a candidate cannot trace is not worth printing.
    """
    if support is not None and not support.backs_term(term):
        return []

    found = [
        Evidence(term=term, where=where, kind=kind, quote=_quote(text))
        for where, kind, text in _places(profile)
        if _mentions(term, text)
    ]
    return found


def backs(term: str, profile: Profile, *, support: Support | None = None) -> bool:
    return bool(find(term, profile, support=support))


def mentions_any(text: str, terms: list[str]) -> list[str]:
    """Which of `terms` a piece of text names. Used to read a document, not a profile."""
    return [term for term in terms if _mentions(term, text)]


def norm_terms(terms: list[str]) -> list[str]:
    return [norm(t) for t in terms]
