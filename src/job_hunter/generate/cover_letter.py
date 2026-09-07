"""Writing the cover letter.

Same rule as the CV, and harder to hold to: a letter is where a model most wants
to help by claiming the candidate is "deeply experienced in" whatever the job
asked for. The contact block is copied from the profile, the letter's body is
checked against it, and the job contributes only its own name, role and
location to the allowed vocabulary - never its list of requirements.

Styling is not decided here. Neutral or company-coloured is a `render` theme.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from ..config import Settings
from ..jobs.models import Job
from ..profile.models import Issue, Personal, Profile, Severity, placeholder_issues
from . import guard, llm, parsing
from .errors import GenerationError
from .facts import profile_block

#: A letter longer than this stops being read.
MAX_PARAGRAPHS = 4

_SYSTEM = """You write a cover letter from a candidate's profile and one job posting.

Rules:
- Every claim about the candidate must already be in the profile. Never add one.
- Never claim a requirement the profile does not support, and never apologise for
  one it lacks. Write about what is there.
- No flattery about the company, no "I am thrilled", no restating the job advert.
- Say what the candidate has done that bears on this job, concretely, using the
  profile's own figures where it has them.
- Three short paragraphs at most. Plain, direct, first person.
- Write in the language of the posting.
- Never write a placeholder. If you do not know a name, address the team.
- Return only JSON matching the requested shape. No prose, no code fences."""

_SHAPE = """{
  "greeting": "",
  "paragraphs": ["", ""],
  "closing": ""
}"""

_NOTES = """Field notes:
- greeting: e.g. "Dear Hiring Team," - a real greeting, never a bracketed placeholder.
- paragraphs: two or three. First: what the candidate does and why this role. Then:
  the specific evidence. Last (optional): a plain closing sentence.
- closing: e.g. "Kind regards," - the name is added afterwards, do not write it."""


class LetterError(GenerationError):
    """The cover letter could not be produced."""


class CoverLetter(BaseModel):
    """One letter, ready to render."""

    #: Copied from the profile, never generated.
    personal: Personal = Field(default_factory=Personal)
    greeting: str = ""
    paragraphs: list[str] = Field(default_factory=list)
    closing: str = ""
    #: Written under the closing. Always the profile's name.
    signature: str = ""
    written_on: str = ""
    company: str = ""
    role: str = ""
    job_label: str = ""
    job_slug: str = ""
    issues: list[Issue] = Field(default_factory=list)

    @property
    def all_issues(self) -> list[Issue]:
        order = {Severity.BLOCKING: 0, Severity.WARNING: 1, Severity.INFO: 2}
        found = [*self.issues]
        found.extend(placeholder_issues(self.greeting, "greeting"))
        found.extend(placeholder_issues(self.paragraphs, "paragraphs"))
        found.extend(placeholder_issues(self.closing, "closing"))
        if not self.paragraphs:
            found.append(Issue(path="paragraphs", severity=Severity.BLOCKING,
                               message="The letter has no body text."))
        if not self.signature:
            found.append(Issue(path="signature", severity=Severity.WARNING,
                               message="No name to sign with - add one to your profile."))
        return sorted(found, key=lambda i: order[i.severity])

    @property
    def blocking(self) -> list[Issue]:
        return [i for i in self.all_issues if i.severity is Severity.BLOCKING]

    @property
    def body(self) -> str:
        """The letter as plain text, for a terminal or a paste into a form."""
        lines = [self.greeting, "", *_spaced(self.paragraphs), self.closing, self.signature]
        return "\n".join(line for line in lines if line is not None).strip()


def _spaced(paragraphs: list[str]) -> list[str]:
    out: list[str] = []
    for paragraph in paragraphs:
        out.extend([paragraph, ""])
    return out


def write(profile: Profile, job: Job, *, settings: Settings | None = None) -> CoverLetter:
    """Write a letter for this job. Raises `LetterError` if it cannot be read back."""
    if not profile.personal.full_name:
        raise LetterError("Add your name to your profile before writing a letter.")
    if (missing := job.missing()) is not None:
        raise LetterError(missing)

    prompt = (
        f"Write a cover letter.\n\nReturn exactly this JSON shape:\n\n{_SHAPE}\n\n"
        f"{_NOTES}\n\n"
        f"=== PROFILE (the only facts you may use) ===\n{profile_block(profile)}\n\n"
        f"=== JOB ===\n{job.brief()}"
    )
    try:
        response = llm.complete(prompt, system=_SYSTEM, settings=settings)
        data = parsing.parse_json(response.text, hint="Try generating again.")
    except parsing.ParseError as exc:
        raise LetterError(str(exc)) from exc

    return assemble(profile, job, data)


def assemble(profile: Profile, job: Job, data: dict) -> CoverLetter:
    """Build the letter from the model's text and the profile's contact facts."""
    paragraphs = _paragraphs(data.get("paragraphs"))[:MAX_PARAGRAPHS]
    greeting = _line(data.get("greeting")) or "Dear Hiring Team,"
    closing = _line(data.get("closing")) or "Kind regards,"

    # A letter may name the company, the role and the place. It may not claim a
    # skill because the posting asked for one, so requirements are not support.
    support = guard.Support.of(profile) | guard.Support.of(
        job.company, job.title, job.location, profile.personal.full_name
    )
    # Only the body is guarded. A greeting is a salutation, not a claim, and the
    # one thing that can go wrong in it - "Dear [Hiring Manager]," - is caught by
    # the placeholder check instead.
    issues = guard.check_all({"paragraphs": paragraphs}, support)

    return CoverLetter(
        personal=profile.personal,
        greeting=greeting,
        paragraphs=paragraphs,
        closing=closing,
        signature=profile.personal.full_name,
        written_on=date.today().isoformat(),
        company=job.company,
        role=job.title,
        job_label=job.label,
        job_slug=job.slug,
        issues=issues,
    )


def _paragraphs(raw: object) -> list[str]:
    if isinstance(raw, str):
        raw = [block for block in raw.split("\n\n")]
    if not isinstance(raw, list):
        return []
    return [text for item in raw if (text := _line(item))]


def _line(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""
