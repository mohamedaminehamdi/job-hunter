"""Tailoring the profile to one job.

The shape of this module is the honesty rule made structural. The model never
writes an employer, a job title, a date, a degree or a certification: it answers
with *indices* into the profile and rewritten bullet text, and everything else is
copied across verbatim. A fabricated employer is therefore not something we
detect and warn about - it cannot be expressed.

What the model does decide: which roles to show and in what order, which of a
role's achievements to keep and how to word them, which projects are relevant,
how to order the skills, and the summary at the top. The free text it produces
goes through `guard` before the document is considered finished.
"""

from __future__ import annotations

from pydantic import Field

from ..config import Settings
from ..jobs.models import Job
from ..profile.models import Issue, Profile, Severity
from . import guard, llm, parsing
from .errors import GenerationError
from .facts import profile_block

#: More than this from one role reads as a job description, not a highlight reel.
MAX_BULLETS = 8

_SYSTEM = """You tailor a CV to one job. You are editing, not writing.

Rules:
- Every claim must already be in the profile you are given. Select, reorder and
  reword what is there; never add anything.
- Do not add employers, titles, dates, degrees, courses, tools or metrics.
- Never restate a requirement from the job as if the candidate met it. If the
  profile does not show it, leave it out. A missing skill is not your problem to solve.
- Prefer the profile's own words for an achievement. Shorten rather than embellish.
- Keep each bullet one sentence, starting with a verb, with any figure copied exactly.
- Order roles by relevance to this job, most relevant first.
- Return only JSON matching the requested shape. No prose, no code fences."""

_SHAPE = """{
  "summary": "",
  "roles": [{"index": 0, "bullets": [""]}],
  "projects": [0],
  "skills": [""]
}"""

_NOTES = """Field notes:
- summary: two or three sentences, first person implied, no "I". Only facts from the profile.
- roles: the roles worth showing, most relevant first, by their index above. Omit a
  role only if it adds nothing for this job. Bullets are that role's achievements,
  reworded for this job; keep the strongest three or four.
- projects: indices of the projects worth showing, most relevant first. May be empty.
- skills: the profile's skills, ordered by relevance to this job. Use the profile's
  own spelling. Do not add a skill the profile does not list."""


class TailorError(GenerationError):
    """The tailored CV could not be produced."""


class TailoredCV(Profile):
    """A CV rewritten for one job.

    A `Profile` subclass, so `report()`, the placeholder check and every template
    that renders a profile work on it unchanged.
    """

    job_label: str = ""
    job_slug: str = ""
    #: Findings from the invention guard and from assembling the document.
    issues: list[Issue] = Field(default_factory=list)

    @property
    def all_issues(self) -> list[Issue]:
        """Guard findings and profile validation together, worst first."""
        order = {Severity.BLOCKING: 0, Severity.WARNING: 1, Severity.INFO: 2}
        return sorted([*self.issues, *self.report()], key=lambda i: order[i.severity])

    @property
    def blocking(self) -> list[Issue]:
        """What must be fixed before this may be exported."""
        return [i for i in self.all_issues if i.severity is Severity.BLOCKING]


def tailor(profile: Profile, job: Job, *, settings: Settings | None = None) -> TailoredCV:
    """Rewrite `profile` for `job`.

    Raises `TailorError` when there is nothing to tailor or the model's answer
    cannot be read. A model that returns a usable document with questionable
    text does not raise: that arrives as issues on the document.
    """
    if not profile.experience and not profile.education:
        raise TailorError(
            "Your profile has no roles and no education, so there is nothing to "
            "tailor. Import your CV first."
        )
    if (missing := job.missing()) is not None:
        raise TailorError(missing)

    prompt = (
        f"Tailor this CV to the job below.\n\nReturn exactly this JSON shape:\n\n{_SHAPE}\n\n"
        f"{_NOTES}\n\n"
        f"=== PROFILE (the only facts you may use) ===\n{profile_block(profile)}\n\n"
        f"=== JOB ===\n{job.brief()}"
    )
    try:
        response = llm.complete(prompt, system=_SYSTEM, settings=settings)
        data = parsing.parse_json(response.text, hint="Try generating again.")
    except parsing.ParseError as exc:
        raise TailorError(str(exc)) from exc

    return assemble(profile, job, data)


def assemble(profile: Profile, job: Job, data: dict) -> TailoredCV:
    """Build the document from the model's choices and the profile's facts.

    Separate from `tailor` so the assembly rules - which are where invention
    would otherwise creep in - can be tested without a model.
    """
    issues: list[Issue] = []

    experience = _roles(profile, data.get("roles"), issues)
    skills = _skills(profile, data.get("skills"), issues)
    projects = _projects(profile, data.get("projects"))
    summary = _text(data.get("summary")) or profile.summary

    document = TailoredCV(
        # Copied, never generated.
        personal=profile.personal,
        education=profile.education,
        certifications=profile.certifications,
        languages=profile.languages,
        # Chosen by the model, from the profile's own facts.
        summary=summary,
        experience=experience,
        projects=projects,
        skills=skills,
        job_label=job.label,
        job_slug=job.slug,
    )

    # The company and role may be named in the summary; nothing else new may be.
    support = guard.Support.of(profile) | guard.Support.of(job.company, job.title)
    issues.extend(guard.check(summary, support, path="summary"))
    for i, role in enumerate(experience):
        issues.extend(guard.check_all(
            {f"experience[{i}].bullets": role.bullets}, guard.Support.of(profile)
        ))

    return document.model_copy(update={"issues": issues})


def _roles(profile: Profile, raw: object, issues: list[Issue]) -> list:
    """Selected roles, with the model's bullets and the profile's identity."""
    chosen: list = []
    seen: set[int] = set()
    for entry in raw if isinstance(raw, list) else []:
        index = _index(entry)
        if index is None or not 0 <= index < len(profile.experience) or index in seen:
            continue
        seen.add(index)
        source = profile.experience[index]
        bullets = _bullets(entry) or source.bullets
        chosen.append(source.model_copy(update={"bullets": bullets[:MAX_BULLETS]}))

    if not chosen and profile.experience:
        issues.append(Issue(
            path="experience", severity=Severity.WARNING,
            message="The model did not select any of your roles, so all of them are "
                    "shown as written in your profile.",
        ))
        return list(profile.experience)
    return chosen


def _skills(profile: Profile, raw: object, issues: list[Issue]) -> list[str]:
    """The model's ordering of skills the profile actually claims.

    Anything the model added is dropped and reported - a skill appearing on a CV
    because the job asked for it is the exact failure this tool exists to avoid.
    """
    known: dict[str, str] = {}
    for skill in profile.skills:
        known.setdefault(skill.strip().lower(), skill)
    for role in profile.experience:
        for skill in role.skills:
            known.setdefault(skill.strip().lower(), skill)
    for project in profile.projects:
        for tech in project.tech:
            known.setdefault(tech.strip().lower(), tech)

    ordered: list[str] = []
    invented: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, str) or not item.strip():
            continue
        match = known.get(item.strip().lower())
        if match is None:
            invented.append(item.strip())
        elif match not in ordered:
            ordered.append(match)

    if invented:
        issues.append(Issue(
            path="skills", severity=Severity.INFO,
            message="Dropped skills the model added but your profile does not list: "
                    + ", ".join(sorted(set(invented))),
        ))
    return ordered or list(profile.skills)


def _projects(profile: Profile, raw: object) -> list:
    """Selected projects, verbatim - project text is not reworded."""
    chosen: list = []
    seen: set[int] = set()
    for entry in raw if isinstance(raw, list) else []:
        index = _index(entry)
        if index is None or not 0 <= index < len(profile.projects) or index in seen:
            continue
        seen.add(index)
        chosen.append(profile.projects[index])
    return chosen


def _index(entry: object) -> int | None:
    """Read an index from the several shapes a model uses to give one."""
    if isinstance(entry, bool):
        return None
    if isinstance(entry, int):
        return entry
    if isinstance(entry, str):
        return int(entry) if entry.strip().isdigit() else None
    if isinstance(entry, dict):
        for key in ("index", "i", "role", "id"):
            if key in entry:
                return _index(entry[key])
    return None


def _bullets(entry: object) -> list[str]:
    if not isinstance(entry, dict):
        return []
    raw = entry.get("bullets") or entry.get("highlights") or []
    if isinstance(raw, str):
        raw = raw.splitlines()
    return [text for item in raw if (text := _text(item))]


def _text(value: object) -> str:
    """A clean single line: strip whitespace and any bullet character."""
    if not isinstance(value, str):
        return ""
    return value.strip().lstrip("-*•–·").strip()
