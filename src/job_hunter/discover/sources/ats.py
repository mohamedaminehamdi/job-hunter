"""Greenhouse, Lever and Ashby: the boards that publish a JSON index.

A large share of tech roles is hosted on one of these three, and all three serve
their whole board over a public, unauthenticated endpoint. No browser, no
login, no scraping - one HTTP request per company returns every open posting
with a title, a location and a permanent link.

The cost is that there is no global index: you have to name the companies. That
is what `criteria.greenhouse` and friends are - a watchlist. `discover.sources.page`
covers the case where you have a URL but not a slug.

Each function here maps one company's payload onto `Listing` and nothing else.
Failure is per company: one dead slug must not lose the other twenty.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx

from ..models import Listing

TIMEOUT = 20

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
LEVER_URL = "https://api.lever.co/v0/postings/{slug}"
ASHBY_URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


class SourceError(RuntimeError):
    """One source could not be searched. Never fatal to a whole search."""


def _get_json(url: str, *, params: dict | None = None, timeout: int = TIMEOUT) -> Any:
    try:
        response = httpx.get(url, params=params, timeout=timeout,
                             follow_redirects=True,
                             headers={"Accept": "application/json"})
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 404:
            raise SourceError(f"No board found at {url} - check the slug.") from exc
        raise SourceError(f"{url} answered {status}.") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise SourceError(f"Could not read {url}: {exc}") from exc


def _iso(value: object) -> str:
    """A date out of whatever the board reports: ISO string or epoch millis."""
    if isinstance(value, (int, float)) and value > 0:
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, UTC).date().isoformat()
    if isinstance(value, str) and len(value) >= 10:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return ""
    return ""


def _clean(text: object, limit: int = 400) -> str:
    """A short plain-text snippet from whatever the board put in the field."""
    if not isinstance(text, str) or not text.strip():
        return ""
    stripped = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", stripped).strip()[:limit]


def greenhouse(slug: str, *, timeout: int = TIMEOUT) -> list[Listing]:
    """Every open posting on one Greenhouse board."""
    payload = _get_json(GREENHOUSE_URL.format(slug=slug), timeout=timeout)
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    listings = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        location = job.get("location") or {}
        listings.append(Listing(
            url=str(job.get("absolute_url", "")),
            title=str(job.get("title", "")),
            company=slug.replace("-", " ").title(),
            location=str(location.get("name", "")) if isinstance(location, dict) else "",
            posted=_iso(job.get("first_published") or job.get("updated_at")),
            source="greenhouse",
        ))
    return [listing for listing in listings if listing.url]


def lever(slug: str, *, timeout: int = TIMEOUT) -> list[Listing]:
    """Every open posting on one Lever board."""
    payload = _get_json(LEVER_URL.format(slug=slug), params={"mode": "json"},
                        timeout=timeout)
    postings = payload if isinstance(payload, list) else []
    listings = []
    for post in postings:
        if not isinstance(post, dict):
            continue
        categories = post.get("categories") or {}
        categories = categories if isinstance(categories, dict) else {}
        listings.append(Listing(
            url=str(post.get("hostedUrl") or post.get("applyUrl") or ""),
            title=str(post.get("text", "")),
            company=slug.replace("-", " ").title(),
            location=str(categories.get("location", "")),
            workplace=str(categories.get("workplaceType", "")),
            employment_type=str(categories.get("commitment", "")),
            posted=_iso(post.get("createdAt")),
            snippet=_clean(post.get("descriptionPlain") or post.get("description")),
            source="lever",
        ))
    return [listing for listing in listings if listing.url]


def ashby(slug: str, *, timeout: int = TIMEOUT) -> list[Listing]:
    """Every open posting on one Ashby board."""
    payload = _get_json(ASHBY_URL.format(slug=slug), timeout=timeout)
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    listings = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        listings.append(Listing(
            url=str(job.get("jobUrl") or job.get("applyUrl") or ""),
            title=str(job.get("title", "")),
            company=str(job.get("organizationName") or slug.replace("-", " ").title()),
            location=str(job.get("location", "")),
            workplace="remote" if job.get("isRemote") else "",
            employment_type=str(job.get("employmentType", "")),
            posted=_iso(job.get("publishedAt")),
            snippet=_clean(job.get("descriptionPlain")),
            source="ashby",
        ))
    return [listing for listing in listings if listing.url]
