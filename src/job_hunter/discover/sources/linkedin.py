"""LinkedIn job search, read as a guest.

Two things to know before relying on this.

It reads the logged-out results page, which is a genuine public page but a
reduced one: fewer results than you see signed in, and LinkedIn shows an
interstitial instead whenever it feels like it. When that happens the source
reports it and the rest of the search carries on.

And LinkedIn's terms prohibit automated access. This is off by default for that
reason - `linkedin: true` in your search criteria is you deciding, not the tool
assuming. The risk it carries is to your own account.
"""

from __future__ import annotations

from urllib.parse import urlencode

from ..criteria import Criteria
from ..models import Listing
from .browser import BrowserError, read

SEARCH_URL = "https://www.linkedin.com/jobs/search"

#: LinkedIn's "date posted" filter is a window in seconds, not a day count.
_WINDOWS = ((1, "r86400"), (7, "r604800"), (30, "r2592000"))

_EXTRACT = """
() => {
  const wall = document.querySelector(
    '.authwall, .join-form, [data-tracking-control-name*="auth_wall"]');
  const cards = document.querySelectorAll(
    'ul.jobs-search__results-list li, div.base-card, div.base-search-card');
  if (!cards.length) return {wall: !!wall, rows: []};

  const pick = (card, selector) => {
    const el = card.querySelector(selector);
    return el ? (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim() : '';
  };
  // The selectors above overlap - a `li` and the `div.base-card` inside it are
  // both cards - so the same posting is reached twice. Keyed by URL, once.
  const rows = new Map();
  for (const card of cards) {
    const link = card.querySelector('a.base-card__full-link, a[href*="/jobs/view/"]');
    if (!link || rows.has(link.href)) continue;
    const time = card.querySelector('time[datetime]');
    rows.set(link.href, {
      url: link.href,
      title: pick(card, '.base-search-card__title, h3'),
      company: pick(card, '.base-search-card__subtitle, h4'),
      location: pick(card, '.job-search-card__location, .base-search-card__metadata span'),
      posted: time ? time.getAttribute('datetime') : '',
    });
  }
  return {wall: false, rows: [...rows.values()]};
}
"""


def _window(days: int) -> str:
    for limit, value in _WINDOWS:
        if days and days <= limit:
            return value
    return ""


def search_url(criteria: Criteria, where: str = "") -> str:
    params = {"keywords": criteria.query, "location": where or criteria.where}
    if window := _window(criteria.posted_within_days):
        params["f_TPR"] = window
    if criteria.remote and not (criteria.hybrid or criteria.onsite):
        params["f_WT"] = "2"  # LinkedIn's code for remote-only
    return f"{SEARCH_URL}?{urlencode({k: v for k, v in params.items() if v})}"


def to_listings(rows: list) -> list[Listing]:
    """The extractor's rows as listings. Separate so it is testable offline."""
    return [
        Listing(
            url=str(row["url"]),
            title=str(row.get("title", "")),
            company=str(row.get("company", "")),
            location=str(row.get("location", "")),
            posted=str(row.get("posted", ""))[:10],
            source="linkedin",
        )
        for row in rows if isinstance(row, dict) and row.get("url")
    ]


def search(criteria: Criteria, *, where: str = "", timeout: int = 30) -> list[Listing]:
    """Public search results for the criteria's primary title."""
    url = search_url(criteria, where)
    payload = read(url, _EXTRACT, timeout=timeout,
                   wait_for="ul.jobs-search__results-list li, div.base-card")
    if not isinstance(payload, dict):
        raise BrowserError("LinkedIn returned a page we could not read.")
    if payload.get("wall"):
        raise BrowserError(
            "LinkedIn showed a sign-in wall instead of results. It does this "
            "intermittently to logged-out visitors - try again later, or search "
            "the company boards under greenhouse/lever/ashby instead."
        )

    return to_listings(payload.get("rows") or [])
