"""Everything the jobhunt skills need, in one file, with nothing to install.

This file is copied byte-identically into every skill that ships a script, so a
skill installed on its own still works. Do not "clean up" the duplication: skills
are installed one at a time and none may import from a sibling that might not be
there. `tools/sync.py` maintains the copies and a test fails if they drift.

Standard library only, and it must stay that way. It also has to run on the
Python people already have - macOS ships 3.9 - so: no StrEnum, no datetime.UTC,
no match statements, no PEP 604 unions outside annotations.

Layout, in dependency order:

    values      coercion, the YAML subset, small text helpers
    model       Profile, Job, and the documents built from them
    guard       is this sentence backed by the profile?
    fit         how well does this CV answer this posting?
    assemble    build a document the model cannot put an employer into
    render      markdown, HTML, and a PDF via the browser you already have
    workspace   where files live
"""

from __future__ import annotations

import dataclasses
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, fields, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

VERSION = "1.0.0"
#: Bumped when a file written here stops being readable by an older skill.
#: Every file carries it, and reading a higher one is an error with a fix.
SCHEMA = 1

UTC = timezone.utc


def now() -> str:
    """Timestamp for an event, in the shape every file uses."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(UTC).date().isoformat()


# --- coercion ---------------------------------------------------------------
#
# Replaces pydantic. Nothing here raises: a profile or a posting arrives from a
# model or from someone's text editor, and the right answer to a malformed field
# is to salvage what parses and report the rest as an issue the user can read.

#: Models answer a string field with a dict about as often as with a sentence,
#: and losing the number is worse than reading it as prose.
def text(value):
    """Flatten whatever landed in a string field into a string."""
    if value is None or isinstance(value, bool):
        return "" if value is None else ("yes" if value else "no")
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    if isinstance(value, dict):
        return ", ".join(f"{k}: {s}" for k, v in value.items() if (s := text(v)))
    if isinstance(value, (list, tuple)):
        return ", ".join(s for v in value if (s := text(v)))
    return str(value).strip()


_BULLET = re.compile(r"^\s*(?:[-*•–·]|\d+[.)])\s*")


def lines(value):
    """Flatten whatever landed in a list field into clean, bullet-free lines."""
    if value is None:
        return []
    if isinstance(value, str):
        candidates = value.splitlines() or [value]
    elif isinstance(value, dict):
        candidates = [text(v) for v in value.values()]
    elif isinstance(value, (list, tuple)):
        candidates = [text(v) for v in value]
    else:
        candidates = [text(value)]
    return [line for c in candidates if (line := _BULLET.sub("", c).strip())]


def build(cls, raw, **overrides):
    """Build a dataclass from loose data. Total: it never raises.

    Each class declares a SHAPE mapping field names to how they coerce - "text",
    "lines", or (list, SomeClass) - and may declare COERCE for the odd field that
    needs its own rule. Anything not mentioned is text.

    `overrides` win over `raw`, which is how facts we observed - a URL, the time
    we fetched it - beat what a model wrote about them.
    """
    if not isinstance(raw, dict):
        raw = {}
    shape = getattr(cls, "SHAPE", {})
    special = getattr(cls, "COERCE", {})
    known = {f.name for f in fields(cls)}
    values = {}

    for name in known:
        if name in overrides:
            given = overrides[name]
        elif name in raw:
            given = raw[name]
        else:
            continue
        kind = shape.get(name, "text")
        try:
            if name in special:
                values[name] = special[name](given)
            elif kind == "lines":
                values[name] = lines(given)
            elif isinstance(kind, tuple) and kind[0] is list:
                items = given if isinstance(given, (list, tuple)) else []
                values[name] = [build(kind[1], item) for item in items
                                if isinstance(item, dict)]
            elif kind == "raw":
                values[name] = given
            else:
                values[name] = text(given)
        except Exception:
            # One unusable field must never lose the record.
            continue
    return cls(**values)


def asdict(obj):
    """A dataclass as plain data, ready for JSON or YAML."""
    return dataclasses.asdict(obj)


# --- YAML, the part of it anyone writes by hand -----------------------------
#
# Hand-written rather than pyyaml, because the whole point of this repo is that
# there is nothing to install. The subset is small for a reason worth knowing:
# every field of every model stored as YAML here is a string or a list of
# strings. Not one int, float or bool. So the reader never guesses a type, and
# the worst parts of YAML - Norway, sexagesimals, 1.0 against "1.0" - cannot
# arise.
#
# It also reports the line. The old reader caught a parse error and returned an
# empty profile, so a typo on line 14 was reported as "a name is required".


class YamlError(ValueError):
    """A YAML file we could not read, and where."""

    def __init__(self, line, message):
        self.line = line
        super().__init__(f"line {line}: {message}")


_KEY = re.compile(r"^(?P<key>[A-Za-z_][\w.-]*)\s*:(?:\s+(?P<value>.*))?$")


class _Literal(str):
    """Text from a | block. Already final, so `_unquote` must leave it alone -
    it is the one value whose leading and trailing whitespace is content."""
_ITEM = re.compile(r"^-(?:\s+(?P<value>.*))?$")


def _unquote(raw, number):
    if isinstance(raw, _Literal):
        return str(raw)
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        body = value[1:-1]
        if value[0] == '"':
            return body.replace('\\"', '"').replace("\\n", "\n")
        return body.replace("''", "'")          # YAML escapes ' inside '...' by doubling
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [_unquote(p, number) for p in inner.split(",")]
    if value.startswith(("&", "*", "!", "{")):
        raise YamlError(number, f"{value[0]!r} is YAML this reader does not do. "
                                "Use plain keys, lists and quoted strings.")
    return value


def _strip_comment(raw):
    """Drop a trailing comment, leaving one inside quotes alone."""
    out, quote = [], ""
    for i, ch in enumerate(raw):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or raw[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip(" \t\r")


def _block(collected, keep_newline):
    body = "\n".join(collected).rstrip("\n")
    return _Literal(body + "\n" if keep_newline and body else body)


def yaml_load(source):
    """Read the subset. Returns a dict. Raises YamlError with a line number."""
    rows = []
    pending = None          # (indent, key, [lines]) while inside a | block
    folding = None          # indent of the row a folded scalar belongs to
    for number, raw in enumerate(source.splitlines(), 1):
        if pending is not None:
            indent, key, collected, keep_newline = pending
            if not raw.strip(" \t\r") or (len(raw) - len(raw.lstrip(" \t"))) > indent:
                collected.append(raw[indent + 2:] if len(raw) > indent + 2 else "")
                continue
            rows.append((indent, key, _block(collected, keep_newline), number))
            pending = None
        line = _strip_comment(raw)
        if not line.strip(" \t\r"):
            # A blank line inside a folded scalar is a paragraph break, which
            # YAML folds to a newline rather than a space.
            if folding is not None and rows:
                last = rows[-1]
                rows[-1] = (last[0], last[1], last[2] + "\n", last[3])
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        body = line.strip(" \t\r")

        # Inside a folded plain scalar every deeper line belongs to it, colon or
        # not. "fleet: we partner on supply deals" is prose, not a key, and only
        # the indent says so. We never write folded scalars; pyyaml does, and
        # people have files it wrote.
        if folding is not None and indent > folding:
            last = rows[-1]
            joiner = "" if last[2].endswith("\n") else " "
            rows[-1] = (last[0], last[1], last[2] + joiner + body, last[3])
            continue
        folding = None

        if body == "---":
            continue
        if (item := _ITEM.match(body)) is not None:
            value = item.group("value")
            rows.append((indent, None, value, number))
            # "- key: value" opens a map, so the deeper lines under it are its
            # sibling keys. "- some text" is a scalar, so they are its folding.
            folding = indent if value and _KEY.match(value) is None else None
            continue
        if (pair := _KEY.match(body)) is not None:
            value = pair.group("value")
            if value is not None and value.strip() in ("|", "|-"):
                # "|" keeps one trailing newline, "|-" strips it. Getting this
                # wrong loses or invents a character at the end of a long text.
                pending = (indent, pair.group("key"), [], value.strip() == "|")
                continue
            rows.append((indent, pair.group("key"), value, number))
            folding = indent if value else None
            continue
        raise YamlError(number, f'expected "key: value" or "- item", got {body[:40]!r}')

    if pending is not None:
        indent, key, collected, keep_newline = pending
        rows.append((indent, key, _block(collected, keep_newline),
                     len(source.splitlines())))

    value, index = _read_block(rows, 0, rows[0][0] if rows else 0)
    return value if isinstance(value, dict) else {}


def _read_block(rows, index, indent):
    """One block at `indent`, as a dict or a list, and where it ended."""
    if index >= len(rows):
        return {}, index
    if rows[index][1] is None:
        out_list = []
        while index < len(rows) and rows[index][0] == indent and rows[index][1] is None:
            _, _, value, number = rows[index]
            index += 1
            if value is None or value == "":
                nested, index = _read_block(rows, index, rows[index][0]) \
                    if index < len(rows) and rows[index][0] > indent else ({}, index)
                out_list.append(nested)
            elif (pair := _KEY.match(value)) is not None:
                # "- key: value" opens a map whose first pair is on the dash line
                item = {pair.group("key"): _unquote(pair.group("value") or "", number)}
                child = indent + 2
                while index < len(rows) and rows[index][0] >= child \
                        and rows[index][1] is not None:
                    nested, index = _read_block(rows, index, rows[index][0])
                    item.update(nested if isinstance(nested, dict) else {})
                out_list.append(item)
            else:
                out_list.append(_unquote(value, number))
        return out_list, index

    out = {}
    while index < len(rows) and rows[index][0] == indent and rows[index][1] is not None:
        _, key, value, number = rows[index]
        index += 1
        if value is None or value == "":
            if index < len(rows) and rows[index][0] > indent:
                out[key], index = _read_block(rows, index, rows[index][0])
            elif index < len(rows) and rows[index][1] is None \
                    and rows[index][0] == indent:
                out[key], index = _read_block(rows, index, indent)
            else:
                out[key] = ""
        else:
            out[key] = _unquote(value, number)
    return out, index


_PLAIN = re.compile(r"^[A-Za-z0-9][\w .,;:/()+&'#@%-]*$")
#: Everything here is a string, but an unquoted 2026 or true or no would come
#: back from any other YAML reader as an int or a bool. Quote them on the way
#: out so the file means the same thing to everyone.
_LOOKS_TYPED = re.compile(
    r"^(?:[-+]?\d[\d,._]*(?:[eE][-+]?\d+)?|0[xob][0-9a-fA-F]+"
    r"|true|false|yes|no|on|off|null|~|\d{4}-\d\d-\d\d.*)$", re.IGNORECASE)


def _scalar(value):
    text_value = "" if value is None else str(value)
    if "\n" in text_value:
        return None                                   # caller writes a | block
    if (text_value == "" or not _PLAIN.match(text_value)
            or _LOOKS_TYPED.match(text_value) or text_value.endswith(" ")
            or ": " in text_value or text_value.endswith(":")):
        return '"' + text_value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text_value


def yaml_dump(data, indent=0):
    """Write the subset back, canonically: two spaces, one value per line.

    Never folds a long line. A folded achievement bullet is exactly the thing a
    person then edits wrongly.
    """
    pad = " " * indent
    out = []
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict) and value:
                out.append(f"{pad}{key}:")
                out.append(yaml_dump(value, indent + 2))
            elif isinstance(value, (list, tuple)):
                if not value:
                    out.append(f"{pad}{key}: []")
                else:
                    out.append(f"{pad}{key}:")
                    out.append(yaml_dump(list(value), indent))
            elif isinstance(value, dict):
                out.append(f"{pad}{key}: {{}}")
            else:
                written = _scalar(value)
                if written is None:
                    body = str(value)
                    out.append(f"{pad}{key}: " + ("|" if body.endswith("\n") else "|-"))
                    out += [f"{pad}  {line}" for line in body.rstrip("\n").splitlines()]
                else:
                    out.append(f"{pad}{key}: {written}")
    elif isinstance(data, (list, tuple)):
        for item in data:
            if isinstance(item, dict) and item:
                body = yaml_dump(item, indent + 2).splitlines()
                out.append(f"{pad}- {body[0].strip()}")
                out += body[1:]
            else:
                written = _scalar(item) or '""'
                out.append(f"{pad}- {written}")
    return "\n".join(out)


# --- model ------------------------------------------------------------------
#
# Loading a profile or a posting NEVER raises. Intake produces partial, messy
# data - a half-parsed PDF, a template with placeholders still in it, a posting
# behind a login wall - and the right response is a checklist the user can act
# on, not a stack trace. Validation reports; it does not reject.

#: Deliberately loose: these catch obvious junk without rejecting unusual-but-real
#: values. Someone's email really can have a + and four dots in it.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_URL = re.compile(r"^https?://\S+$")
_PLACEHOLDER = re.compile(r"\[.*?\]|^your |^enter |\bTBD\b|\bXXX\b", re.IGNORECASE)
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_HEX = re.compile(r"^#(?:[0-9a-f]{3}|[0-9a-f]{6})$", re.IGNORECASE)

#: Severities, worst first. Plain strings because 3.9 has no StrEnum and these
#: are written to YAML, read back, and compared against literals in templates.
BLOCKING = "blocking"   # no usable document can be produced
WARNING = "warning"     # usable, but visibly worse
INFO = "info"           # worth filling in eventually
SEVERITIES = (BLOCKING, WARNING, INFO)


@dataclass
class Issue:
    """One problem with one field, addressed to the person fixing it."""

    path: str = ""
    severity: str = WARNING
    message: str = ""

    def __str__(self):
        return f"[{self.severity}] {self.path}: {self.message}"


def placeholder_issues(value, path=""):
    """Every string inside `value` that is still template text, e.g. '[Your Name]'.

    This is the failure that silently reached a real PDF in the tool this one
    replaces, so it is checked explicitly rather than hoped about - on profiles,
    and on everything a generator writes.
    """
    found = []

    def walk(current, at):
        if isinstance(current, Issue):
            return  # diagnostics describe content; they are not content
        if isinstance(current, str):
            if current and _PLACEHOLDER.search(current):
                found.append(Issue(at or "text", BLOCKING,
                                   f"Unfilled placeholder text: {current[:40]!r}"))
        elif dataclasses.is_dataclass(current):
            for f in fields(current):
                walk(getattr(current, f.name), f"{at}.{f.name}" if at else f.name)
        elif isinstance(current, dict):
            for key, item in current.items():
                walk(item, f"{at}.{key}" if at else str(key))
        elif isinstance(current, (list, tuple)):
            for i, item in enumerate(current):
                walk(item, f"{at}[{i}]")

    walk(value, path)
    return found


def _period(start, end):
    return f"{start} - {end}" if start and end else (start or end)


@dataclass
class Personal:
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
    def full_name(self):
        return " ".join(p for p in (self.name, self.surname) if p)


@dataclass
class Role:
    position: str = ""
    company: str = ""
    start: str = ""
    end: str = ""
    location: str = ""
    industry: str = ""
    #: Free-text achievements. The tailorer selects and rewrites these; it must
    #: not introduce claims absent from here.
    bullets: list = field(default_factory=list)
    skills: list = field(default_factory=list)

    SHAPE = {"bullets": "lines", "skills": "lines"}

    @property
    def period(self):
        return _period(self.start, self.end)


@dataclass
class Education:
    level: str = ""
    institution: str = ""
    field_of_study: str = ""
    start: str = ""
    end: str = ""
    grade: str = ""
    location: str = ""
    #: Named courses. Empty means "omit the section" - never "invent some".
    courses: list = field(default_factory=list)

    SHAPE = {"courses": "lines"}

    @property
    def period(self):
        return _period(self.start, self.end)


@dataclass
class Project:
    name: str = ""
    description: str = ""
    link: str = ""
    tech: list = field(default_factory=list)

    SHAPE = {"tech": "lines"}


@dataclass
class Certification:
    name: str = ""
    issuer: str = ""
    year: str = ""
    description: str = ""


@dataclass
class Language:
    name: str = ""
    level: str = ""


@dataclass
class Profile:
    """Everything known about the user. Every field optional by construction."""

    personal: Personal = field(default_factory=Personal)
    summary: str = ""
    experience: list = field(default_factory=list)
    education: list = field(default_factory=list)
    projects: list = field(default_factory=list)
    skills: list = field(default_factory=list)
    certifications: list = field(default_factory=list)
    languages: list = field(default_factory=list)

    SHAPE = {
        "personal": "raw",
        "experience": (list, Role),
        "education": (list, Education),
        "projects": (list, Project),
        "certifications": (list, Certification),
        "languages": (list, Language),
        "skills": "lines",
    }
    COERCE = {"personal": lambda v: build(Personal, v)}

    def report(self):
        """Every problem worth showing the user, worst first."""
        issues = []
        p = self.personal

        if not p.full_name:
            issues.append(Issue("personal.name", BLOCKING,
                                "A name is required to render a CV."))
        if not self.experience and not self.education:
            issues.append(Issue("experience", BLOCKING,
                                "Add at least one role or one degree."))

        if not p.email:
            issues.append(Issue("personal.email", WARNING,
                                "No email - employers cannot reply."))
        elif not _EMAIL.match(p.email):
            issues.append(Issue("personal.email", WARNING,
                                f"{p.email!r} does not look like an email address."))

        for name in ("github", "linkedin", "website"):
            value = getattr(p, name)
            if value and not _URL.match(value):
                issues.append(Issue(f"personal.{name}", WARNING,
                                    f"{value!r} should start with http:// or https://."))

        for i, role in enumerate(self.experience):
            where = f"experience[{i}]"
            if not role.position or not role.company:
                issues.append(Issue(where, WARNING,
                                    "Role needs both a position and a company."))
            if not role.bullets:
                issues.append(Issue(f"{where}.bullets", WARNING,
                                    f"No achievements for {role.company or 'this role'} - "
                                    "the tailorer has nothing to work with."))

        issues.extend(placeholder_issues(self))

        if not self.skills:
            issues.append(Issue("skills", INFO,
                                "Listing skills improves keyword matching."))
        if not self.summary:
            issues.append(Issue("summary", INFO,
                                "A summary gives the tailorer a voice to match."))

        order = {BLOCKING: 0, WARNING: 1, INFO: 2}
        return sorted(issues, key=lambda i: order.get(i.severity, 3))

    def blocking_issues(self):
        """The issues that stop a document being exported."""
        return [i for i in self.report() if i.severity == BLOCKING]

    @property
    def is_renderable(self):
        """True when nothing blocking remains."""
        return not self.blocking_issues()


#: Long enough to tailor against. Below this the description is a stub or a
#: cookie banner, and generating from it produces confident nonsense.
MIN_DESCRIPTION = 120


def _colour(value):
    """Only a hex colour survives: this reaches a stylesheet."""
    body = text(value)
    if body.startswith("#") and len(body) == 4:  # #abc -> #aabbcc
        body = "#" + "".join(c * 2 for c in body[1:])
    return body.lower() if _HEX.match(body) else ""


@dataclass
class Job:
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
    responsibilities: list = field(default_factory=list)
    #: Stated as required. The tailorer answers these first.
    requirements: list = field(default_factory=list)
    nice_to_have: list = field(default_factory=list)
    #: Terms worth mirroring *where the profile supports them* - never otherwise.
    keywords: list = field(default_factory=list)
    #: Language the posting is written in, so we can answer in it.
    language: str = ""
    #: The company's colour, read off the page - not guessed by a model.
    brand_color: str = ""
    #: The page text the model read. Kept so review can show its working.
    source_text: str = ""
    fetched_at: str = ""

    SHAPE = {
        "responsibilities": "lines", "requirements": "lines",
        "nice_to_have": "lines", "keywords": "lines",
    }
    COERCE = {"brand_color": _colour}

    def __post_init__(self):
        # The one field worth coercing even on direct construction: it reaches a
        # stylesheet. `render.branded` refuses non-hex too - this is the inner of
        # the two checks, so a Job never carries a colour that is not one.
        self.brand_color = _colour(self.brand_color)

    @property
    def label(self):
        """One line naming the job, for logs, menus and page titles."""
        if self.title and self.company:
            return f"{self.title} at {self.company}"
        return self.title or self.company or self.url or "Untitled job"

    @property
    def slug(self):
        """Filesystem-safe stem for the documents generated for this job."""
        stem = _SLUG_STRIP.sub("-", f"{self.company} {self.title}".lower()).strip("-")
        return stem[:60] or "job"

    @property
    def detail_lines(self):
        """Every stated requirement and responsibility, in priority order."""
        return [*self.requirements, *self.responsibilities, *self.nice_to_have]

    def missing(self):
        """Why this job cannot be tailored against, or None to proceed."""
        if not (self.description or self.detail_lines):
            return ("This posting has no description to work from. Paste the job "
                    "description text instead of the URL.")
        if len(self.description) < MIN_DESCRIPTION and len(self.detail_lines) < 3:
            return ("Only a fragment of this posting came through - probably a login "
                    "wall or a page that renders its description late. Paste the job "
                    "description text instead.")
        return None

    @property
    def is_usable(self):
        return self.missing() is None

    def brief(self):
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
        for name, body in (("Responsibilities", self.responsibilities),
                           ("Requirements", self.requirements),
                           ("Nice to have", self.nice_to_have)):
            if body:
                parts.append(f"\n{name}:\n" + "\n".join(f"- {line}" for line in body))
        if self.description:
            parts.append(f"\nDescription:\n{self.description}")
        if self.keywords:
            parts.append(f"\nKeywords: {', '.join(self.keywords)}")
        return "\n".join(parts).strip()


# --- documents on disk ------------------------------------------------------
#
# One pair of functions for every record this project stores, because they are
# all the same shape: a dataclass, a YAML file, and a rule that reading must
# never raise. A malformed file is an empty record plus an issue to show, not a
# traceback - the file is somebody's hand-edited YAML as often as ours.


def load(cls, path, **overrides):
    """Read a record from YAML. Returns an empty one if there is nothing there.

    Malformed YAML yields an empty record rather than raising: something always
    has to be shown to the user, and `report()` is where they find out what is
    wrong with it.
    """
    path = Path(path)
    if not path.exists():
        return build(cls, {}, **overrides)
    try:
        raw = yaml_load(path.read_text(encoding="utf-8"))
    except (YamlError, OSError, UnicodeDecodeError):
        raw = {}
    return build(cls, raw, **overrides)


def save(obj, path):
    """Write a record as YAML, creating the directory if needed.

    Written to a temporary file and moved into place, so an interrupted write
    cannot leave a half-written profile where a whole one used to be.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml_dump(asdict(obj))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(body + "\n", encoding="utf-8")
    tmp.replace(path)
    return path
