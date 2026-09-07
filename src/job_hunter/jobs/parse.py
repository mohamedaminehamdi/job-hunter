"""Turning a scraped page - or pasted text - into a `Job`.

The split mirrors CV intake: getting the text is deterministic (`jobs.fetch`),
understanding it is generation. Job pages are worse than CVs to parse, because
the description arrives surrounded by "similar jobs", cookie notices and a
company boilerplate paragraph, so a model earns its place here.

The same honesty rule applies in reverse: this must not invent requirements.
An imagined requirement propagates into a tailored CV as an imagined skill.
"""

from __future__ import annotations

from ..config import Settings
from ..generate import llm, parsing
from . import fetch as fetch_module
from .fetch import FetchError, PageSource
from .models import Job, from_dict, now

#: Postings run long (benefits, legal boilerplate, EEO statements). This keeps
#: the prompt bounded without paying for tokens that say nothing about the role.
MAX_CHARS = 24_000
#: Requirements cluster at the end of a posting, so keep both ends, not just the head.
_TAIL_CHARS = 6_000

_SYSTEM = """You extract structured data from job postings.

Rules:
- Copy requirements and responsibilities close to verbatim. Do not soften or embellish them.
- Never invent. If the posting does not state something, leave that field empty.
- Do not infer a salary, a seniority level or a location that is not written down.
- Distinguish hard requirements from nice-to-haves only where the posting itself does;
  when it does not, treat everything stated as a requirement.
- Ignore page furniture: cookie notices, similar jobs, application instructions,
  benefits lists and legal statements.
- Return only JSON matching the requested shape. No prose, no code fences."""

_SHAPE = """{
  "title": "",
  "company": "",
  "location": "",
  "workplace": "",
  "employment_type": "",
  "salary": "",
  "description": "",
  "responsibilities": [""],
  "requirements": [""],
  "nice_to_have": [""],
  "keywords": [""],
  "language": ""
}"""

_FIELD_NOTES = """Field notes:
- workplace: remote, hybrid or on-site, only if stated.
- description: two or three sentences on what the role is. Not a sales pitch for the company.
- keywords: the concrete tools, languages and domain terms this posting screens for.
- language: ISO 639-1 code of the language the posting is written in, e.g. "en", "fr"."""


class ParseError(RuntimeError):
    """The page loaded but could not be read as a job posting."""


def from_url(url: str, *, timeout: int = fetch_module.DEFAULT_TIMEOUT,
             settings: Settings | None = None) -> Job:
    """Fetch a job page and parse it. The whole path, for one URL.

    Raises `FetchError` if the page cannot be read and `ParseError` if it can be
    read but not understood - the two need different advice, so they stay apart.
    """
    return from_page(fetch_module.fetch(url, timeout=timeout), settings=settings)


def from_page(page: PageSource, *, settings: Settings | None = None) -> Job:
    """Parse an already-fetched page, keeping what we read off it for certain."""
    return from_text(page.text, url=page.url, page_title=page.title,
                     brand_color=page.brand_color, settings=settings)


def from_text(text: str, *, url: str = "", page_title: str = "", brand_color: str = "",
              settings: Settings | None = None) -> Job:
    """Parse job description text, pasted or scraped.

    The URL, brand colour and fetch time are set from what we know rather than
    what the model says, and the source text travels with the Job so review can
    show what was read.
    """
    if not text.strip():
        raise ParseError("Nothing to parse - the job description is empty.")

    prompt = _prompt(trim(text), page_title)
    try:
        response = llm.complete(prompt, system=_SYSTEM, settings=settings)
        data = parsing.parse_json(
            response.text, hint="Try again, or paste the job description as text."
        )
    except parsing.ParseError as exc:
        raise ParseError(str(exc)) from exc

    return from_dict(data, url=url, brand_color=brand_color, source_text=text,
                     fetched_at=now())


def _prompt(text: str, page_title: str) -> str:
    hint = (
        f"The browser reported the page title as {page_title!r}; it usually names "
        "the role and the company, but trust the page text over it.\n\n"
        if page_title
        else ""
    )
    return (
        f"Extract this job posting into exactly this JSON shape:\n\n{_SHAPE}\n\n"
        f"{_FIELD_NOTES}\n\n"
        "Omit any array entry you would otherwise fill with an empty string.\n\n"
        f"{hint}"
        f"Posting:\n---\n{text}\n---"
    )


def trim(text: str, limit: int = MAX_CHARS) -> str:
    """Cut an over-long posting from the middle, keeping both ends.

    Boilerplate lives in the middle; the role is at the top and the requirements
    are at the bottom, so dropping the head would lose the job title.
    """
    text = text.strip()
    if len(text) <= limit:
        return text
    head = text[: limit - _TAIL_CHARS]
    tail = text[-_TAIL_CHARS:]
    return f"{head}\n\n[... {len(text) - limit} characters omitted ...]\n\n{tail}"


__all__ = ["from_url", "from_page", "from_text", "trim", "ParseError", "FetchError"]
