"""What a job posting is, once the noise is stripped off it.

A `Job` is the other half of the tailoring input: the profile says what is true,
the job says what matters. Nothing here knows about the profile, and nothing
here calls a model - `jobs.parse` does that and hands the result over.

Like `Profile`, this never raises on bad input. A posting behind a login wall or
a description a model half-understood should arrive as a sparse `Job` the UI can
show, not an exception.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

#: Long enough to tailor against. Below this the description is a stub or a
#: cookie banner, and generating from it produces confident nonsense.
MIN_DESCRIPTION = 120

#: Fields a model may answer in the wrong shape, coerced on the way in.
_STR_FIELDS = (
    "url", "title", "company", "location", "workplace",
    "employment_type", "salary", "description", "language",
)
_LIST_FIELDS = ("responsibilities", "requirements", "nice_to_have", "keywords")

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_HEX = re.compile(r"^#(?:[0-9a-f]{3}|[0-9a-f]{6})$", re.IGNORECASE)
_BULLET = re.compile(r"^\s*(?:[-*•–·]|\d+[.)])\s*")


def _scalar(value: object) -> str:
    """Flatten whatever landed in a string field into a string.

    Models answer `salary` with `{"min": 60000, "max": 80000}` about as often as
    with a sentence, and losing the number is worse than reading it as prose.
    """
    if value is None or isinstance(value, bool):
        return "" if value is None else ("yes" if value else "no")
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        parts = [f"{k}: {s}" for k, v in value.items() if (s := _scalar(v))]
        return ", ".join(parts)
    if isinstance(value, list):
        return ", ".join(s for v in value if (s := _scalar(v)))
    return str(value).strip()


def _lines(value: object) -> list[str]:
    """Flatten whatever landed in a list field into clean, bullet-free lines."""
    if value is None:
        return []
    if isinstance(value, str):
        candidates = value.splitlines() or [value]
    elif isinstance(value, dict):
        candidates = [_scalar(v) for v in value.values()]
    elif isinstance(value, list):
        candidates = [_scalar(v) for v in value]
    else:
        candidates = [_scalar(value)]
    return [line for c in candidates if (line := _BULLET.sub("", c).strip())]


class Job(BaseModel):
    """One posting, as far as we understand it."""

    url: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    #: remote / hybrid / on-site, in the posting's own words where it says.
    workplace: str = ""
    employment_type: str = ""
    salary: str = ""
    #: What the role is, in a paragraph or two.
    description: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    #: Stated as required. The tailorer answers these first.
    requirements: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    #: Terms worth mirroring *where the profile supports them* - never otherwise.
    keywords: list[str] = Field(default_factory=list)
    #: Language the posting is written in, so we can answer in it.
    language: str = ""
    #: The company's colour, read off the page - not guessed by a model. Drives
    #: the company-branded cover letter theme.
    brand_color: str = ""
    #: The page text the model read. Kept so review can show its working.
    source_text: str = ""
    fetched_at: str = ""

    @field_validator(*_STR_FIELDS, mode="before")
    @classmethod
    def _coerce_scalar(cls, value: object) -> str:
        return _scalar(value)

    @field_validator(*_LIST_FIELDS, mode="before")
    @classmethod
    def _coerce_list(cls, value: object) -> list[str]:
        return _lines(value)

    @field_validator("brand_color", mode="before")
    @classmethod
    def _coerce_colour(cls, value: object) -> str:
        """Only a hex colour survives: this reaches a stylesheet."""
        text = _scalar(value)
        if text.startswith("#") and len(text) == 4:  # #abc -> #aabbcc
            text = "#" + "".join(c * 2 for c in text[1:])
        return text.lower() if _HEX.match(text) else ""

    @property
    def label(self) -> str:
        """One line naming the job, for logs, menus and page titles."""
        if self.title and self.company:
            return f"{self.title} at {self.company}"
        return self.title or self.company or self.url or "Untitled job"

    @property
    def slug(self) -> str:
        """Filesystem-safe stem for the documents generated for this job."""
        stem = _SLUG_STRIP.sub("-", f"{self.company} {self.title}".lower()).strip("-")
        return stem[:60] or "job"

    @property
    def detail_lines(self) -> list[str]:
        """Every stated requirement and responsibility, in priority order."""
        return [*self.requirements, *self.responsibilities, *self.nice_to_have]

    def missing(self) -> str | None:
        """Human-readable reason this job cannot be tailored against, if any.

        Mirrors `Settings.missing()`: a reason to show, or None to proceed.
        """
        if not (self.description or self.detail_lines):
            return (
                "This posting has no description to work from. Paste the job "
                "description text instead of the URL."
            )
        if len(self.description) < MIN_DESCRIPTION and len(self.detail_lines) < 3:
            return (
                "Only a fragment of this posting came through - probably a login "
                "wall or a page that renders its description late. Paste the job "
                "description text instead."
            )
        return None

    @property
    def is_usable(self) -> bool:
        """True when there is enough here to tailor against."""
        return self.missing() is None

    def brief(self) -> str:
        """The job as a prompt block: compact, ordered, no empty sections.

        Every generator builds its prompt from this, so a change to how a job is
        presented to a model happens once.
        """
        head = [
            ("Role", self.title),
            ("Company", self.company),
            ("Location", " - ".join(p for p in (self.location, self.workplace) if p)),
            ("Employment", self.employment_type),
            ("Salary", self.salary),
            ("Posting language", self.language),
        ]
        parts = [f"{name}: {value}" for name, value in head if value]

        for name, lines in (
            ("Responsibilities", self.responsibilities),
            ("Requirements", self.requirements),
            ("Nice to have", self.nice_to_have),
        ):
            if lines:
                parts.append(f"\n{name}:\n" + "\n".join(f"- {line}" for line in lines))
        if self.description:
            parts.append(f"\nDescription:\n{self.description}")
        if self.keywords:
            parts.append(f"\nKeywords: {', '.join(self.keywords)}")
        return "\n".join(parts).strip()


def from_dict(raw: dict, **overrides: object) -> Job:
    """Build a Job from loose data, dropping unknown keys.

    Overrides win over the data: the URL and fetch time are things we know for
    certain and the model only guesses at.
    """
    known = {k: v for k, v in raw.items() if k in Job.model_fields}
    known.update(overrides)
    try:
        return Job.model_validate(known)
    except Exception:
        # Salvage what parses. One unusable field should not lose the posting.
        job = Job()
        for key, value in known.items():
            try:
                validated = Job.model_validate({key: value})
                job = job.model_copy(update={key: getattr(validated, key)})
            except Exception:
                continue
        return job


def now() -> str:
    """Timestamp for `fetched_at`, in one place so tests can rely on the shape."""
    return datetime.now(UTC).isoformat(timespec="seconds")
