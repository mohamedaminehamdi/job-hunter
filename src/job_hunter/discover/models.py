"""What a search hit is, before anyone has looked closely at it.

A `Listing` is deliberately not a `Job`. A search returns fifty of these and
most will be discarded, so a listing holds only what a board hands over cheaply
in its result list - title, company, location, a link. Turning one into a `Job`
costs a page load and a model call, and only happens to the ones you pick.

Identity matters more here than anywhere else in the tool: the same posting will
come back from every source you have enabled, every time you search. So a
listing carries a stable id derived from its URL, and the queue is keyed by it.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import BaseModel, Field

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")

#: Query parameters that identify the click, not the posting. Boards append
#: these freely, and without stripping them one job arrives as five.
_TRACKING = re.compile(
    r"^(utm_|ref$|refid$|trk$|trackingid$|src$|source$|gh_src$|lever-source|"
    r"originalsubdomain$|position$|pagenum$|eid$|from$|tk$|vjk$|jsa$)",
    re.IGNORECASE,
)


def slugify(text: str, limit: int = 50) -> str:
    return _SLUG_STRIP.sub("-", text.lower()).strip("-")[:limit]


def canonical_url(url: str) -> str:
    """The posting's address with the click-tracking taken off.

    Two links to one job differ only in their tracking, so this is what identity
    is computed from - not the URL as pasted.
    """
    parsed = urlparse(url.strip())
    kept = [(k, v) for k, v in parse_qsl(parsed.query) if not _TRACKING.match(k)]
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip("/") or "/",
        "",
        urlencode(sorted(kept)),
        "",
    ))


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Listing(BaseModel):
    """One result from one source. Enough to decide whether to look closer."""

    url: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    #: remote / hybrid / on-site, only when the source states it.
    workplace: str = ""
    employment_type: str = ""
    #: ISO date the posting went up, when the source gives one.
    posted: str = ""
    #: A line or two of description, when the source's result list carries it.
    #: Never fetched separately - that is what picking the listing is for.
    snippet: str = ""
    #: Which adapter found it: greenhouse, lever, linkedin, page, ...
    source: str = ""
    found_at: str = Field(default_factory=now)

    @property
    def id(self) -> str:
        """Stable across searches and across sources. The queue is keyed by it.

        Readable first, unique second: the hash suffix is what actually
        guarantees two different postings never collide, but nobody can type
        `a3f9c1`, so the company and title lead.
        """
        digest = hashlib.sha1(canonical_url(self.url).encode()).hexdigest()[:6]
        stem = slugify(f"{self.company} {self.title}") or self.source or "listing"
        return f"{stem}-{digest}"

    @property
    def label(self) -> str:
        if self.title and self.company:
            return f"{self.title} at {self.company}"
        return self.title or self.company or self.url or "Untitled listing"

    @property
    def age_days(self) -> int | None:
        """Days since the posting went up, or None when the source is silent."""
        if not self.posted:
            return None
        try:
            posted = date.fromisoformat(self.posted[:10])
        except ValueError:
            return None
        return max((datetime.now(UTC).date() - posted).days, 0)

    @property
    def text(self) -> str:
        """Everything a listing says, for the matcher to read."""
        return "\n".join(p for p in (self.title, self.company, self.location,
                                     self.workplace, self.employment_type,
                                     self.snippet) if p)


class Match(BaseModel):
    """Why a listing is - or is not - worth your time."""

    score: int = 0
    #: Plain sentences, shown to the user. A bare number explains nothing.
    reasons: list[str] = Field(default_factory=list)
    #: Set when a blacklist or a filter ruled the listing out entirely.
    excluded: str = ""

    @property
    def is_excluded(self) -> bool:
        return bool(self.excluded)


class Candidate(BaseModel):
    """A listing, its score, and what you decided about it."""

    listing: Listing = Field(default_factory=Listing)
    match: Match = Field(default_factory=Match)
    #: new -> you have not looked; picked -> promoted to a saved job;
    #: dismissed -> never show it again. Decisions survive re-searching.
    status: str = "new"
    decided_at: str = ""
    #: Slug of the `Job` this became, once picked.
    job_slug: str = ""

    @property
    def id(self) -> str:
        return self.listing.id
