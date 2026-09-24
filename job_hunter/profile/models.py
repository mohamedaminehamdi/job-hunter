"""The user's career profile: the single source of truth every generator reads.

Design rule: loading a profile NEVER raises. Intake produces partial, messy data
(a half-parsed PDF, a template with placeholders still in it) and the UI needs to
show that as a checklist, not a stack trace. Validation therefore returns warnings
via `Profile.report()` instead of rejecting the document.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field

# Deliberately loose: these catch obvious junk (unfilled placeholders, a bare
# word where a URL belongs) without rejecting unusual-but-real values.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_URL = re.compile(r"^https?://\S+$")
_PLACEHOLDER = re.compile(r"\[.*?\]|^your |^enter |\bTBD\b|\bXXX\b", re.IGNORECASE)


class Severity(StrEnum):
    #: Generators cannot produce a usable document without this.
    BLOCKING = "blocking"
    #: Usable, but the output will be visibly worse.
    WARNING = "warning"
    #: Worth filling in eventually.
    INFO = "info"


class Issue(BaseModel):
    """One problem with one field, addressed to the person fixing it."""

    path: str
    severity: Severity
    message: str

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"[{self.severity.value}] {self.path}: {self.message}"


def placeholder_issues(value: object, path: str = "") -> list[Issue]:
    """Every string inside `value` that is still template text, e.g. '[Your Name]'.

    This is the failure that silently reached a real PDF in the tool this one
    replaces, so it is checked explicitly rather than hoped about - on profiles,
    and on everything a generator writes.
    """
    found: list[Issue] = []

    def walk(current: object, at: str) -> None:
        if isinstance(current, str):
            if current and _PLACEHOLDER.search(current):
                found.append(Issue(path=at or "text", severity=Severity.BLOCKING,
                                   message=f"Unfilled placeholder text: {current[:40]!r}"))
        elif isinstance(current, Issue):
            pass  # diagnostics describe content; they are not content
        elif isinstance(current, BaseModel):
            for name in type(current).model_fields:
                walk(getattr(current, name), f"{at}.{name}" if at else name)
        elif isinstance(current, (list, tuple)):
            for i, item in enumerate(current):
                walk(item, f"{at}[{i}]")

    walk(value, path)
    return found


class Personal(BaseModel):
    name: str = ""
    surname: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    country: str = ""
    github: str = ""
    linkedin: str = ""
    website: str = ""

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.name, self.surname) if p)


class Role(BaseModel):
    position: str = ""
    company: str = ""
    start: str = ""
    end: str = ""
    location: str = ""
    industry: str = ""
    #: Free-text achievements. The tailorer selects and rewrites these; it must
    #: not introduce claims absent from here.
    bullets: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)

    @property
    def period(self) -> str:
        if self.start and self.end:
            return f"{self.start} - {self.end}"
        return self.start or self.end


class Education(BaseModel):
    level: str = ""
    institution: str = ""
    field_of_study: str = ""
    start: str = ""
    end: str = ""
    grade: str = ""
    location: str = ""
    #: Named courses. Empty means "omit the section" - never "invent some".
    courses: list[str] = Field(default_factory=list)

    @property
    def period(self) -> str:
        if self.start and self.end:
            return f"{self.start} - {self.end}"
        return self.start or self.end


class Project(BaseModel):
    name: str = ""
    description: str = ""
    link: str = ""
    tech: list[str] = Field(default_factory=list)


class Certification(BaseModel):
    name: str = ""
    issuer: str = ""
    year: str = ""
    description: str = ""


class Language(BaseModel):
    name: str = ""
    level: str = ""


class Profile(BaseModel):
    """Everything known about the user. Every field optional by construction."""

    personal: Personal = Field(default_factory=Personal)
    summary: str = ""
    experience: list[Role] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)

    def report(self) -> list[Issue]:
        """Every problem worth showing the user, worst first."""
        issues: list[Issue] = []
        p = self.personal

        if not p.full_name:
            issues.append(Issue(path="personal.name", severity=Severity.BLOCKING,
                                message="A name is required to render a CV."))
        if not self.experience and not self.education:
            issues.append(Issue(path="experience", severity=Severity.BLOCKING,
                                message="Add at least one role or one degree."))

        if not p.email:
            issues.append(Issue(path="personal.email", severity=Severity.WARNING,
                                message="No email - employers cannot reply."))
        elif not _EMAIL.match(p.email):
            issues.append(Issue(path="personal.email", severity=Severity.WARNING,
                                message=f"{p.email!r} does not look like an email address."))

        for field in ("github", "linkedin", "website"):
            value = getattr(p, field)
            if value and not _URL.match(value):
                issues.append(Issue(path=f"personal.{field}", severity=Severity.WARNING,
                                    message=f"{value!r} should start with http:// or https://."))

        for i, role in enumerate(self.experience):
            where = f"experience[{i}]"
            if not role.position or not role.company:
                issues.append(Issue(path=where, severity=Severity.WARNING,
                                    message="Role needs both a position and a company."))
            if not role.bullets:
                issues.append(Issue(path=f"{where}.bullets", severity=Severity.WARNING,
                                    message=f"No achievements for {role.company or 'this role'} - "
                                            "the tailorer has nothing to work with."))

        issues.extend(self._placeholder_issues())

        if not self.skills:
            issues.append(Issue(path="skills", severity=Severity.INFO,
                                message="Listing skills improves keyword matching."))
        if not self.summary:
            issues.append(Issue(path="summary", severity=Severity.INFO,
                                message="A summary gives the tailorer a voice to match."))

        order = {Severity.BLOCKING: 0, Severity.WARNING: 1, Severity.INFO: 2}
        return sorted(issues, key=lambda i: order[i.severity])

    def _placeholder_issues(self) -> list[Issue]:
        return placeholder_issues(self)

    @property
    def is_renderable(self) -> bool:
        """True when nothing blocking remains."""
        return not any(i.severity == Severity.BLOCKING for i in self.report())
