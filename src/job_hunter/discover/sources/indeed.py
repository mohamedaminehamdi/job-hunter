"""Indeed job search.

The same two warnings as LinkedIn, more so. Indeed sits behind an anti-bot
challenge that a headless browser trips regularly, so expect this source to
report a block as often as it reports results. When it is blocked it says so and
the rest of the search continues.

Off by default. `indeed: true` in your criteria is your decision.
"""

from __future__ import annotations

from urllib.parse import urlencode

from ..criteria import Criteria
from ..models import Listing
from .browser import BrowserError, read

SEARCH_URL = "https://www.indeed.com/jobs"

_EXTRACT = """
() => {
  const title = (document.title || '').toLowerCase();
  const blocked = !!document.querySelector(
                    '#challenge-form, .cf-challenge, form[action*="challenge"]')
                  || title.includes('just a moment')
                  || title.includes('additional verification');
  const cards = document.querySelectorAll('.job_seen_beacon, [data-testid="slider_item"]');
  if (!cards.length) return {blocked, rows: []};

  const pick = (card, selector) => {
    const el = card.querySelector(selector);
    return el ? (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim() : '';
  };
  // Two selectors can reach the same posting, so key by URL and take it once.
  const rows = new Map();
  for (const card of cards) {
    const link = card.querySelector('h2.jobTitle a, a.jcs-JobTitle');
    if (!link || rows.has(link.href)) continue;
    rows.set(link.href, {
      url: link.href,
      title: pick(card, 'h2.jobTitle'),
      company: pick(card, '[data-testid="company-name"]'),
      location: pick(card, '[data-testid="text-location"]'),
      snippet: pick(card, '[data-testid="belowJobSnippet"], .job-snippet'),
    });
  }
  return {blocked: false, rows: [...rows.values()]};
}
"""


def search_url(criteria: Criteria, where: str = "") -> str:
    params = {"q": criteria.query, "l": where or criteria.where}
    if criteria.posted_within_days:
        params["fromage"] = str(criteria.posted_within_days)
    return f"{SEARCH_URL}?{urlencode({k: v for k, v in params.items() if v})}"


def to_listings(rows: list) -> list[Listing]:
    """The extractor's rows as listings. Separate so it is testable offline."""
    return [
        Listing(
            url=str(row["url"]),
            title=str(row.get("title", "")),
            company=str(row.get("company", "")),
            location=str(row.get("location", "")),
            snippet=str(row.get("snippet", "")),
            source="indeed",
        )
        for row in rows if isinstance(row, dict) and row.get("url")
    ]


def search(criteria: Criteria, *, where: str = "", timeout: int = 30) -> list[Listing]:
    url = search_url(criteria, where)
    payload = read(url, _EXTRACT, timeout=timeout,
                   wait_for='.job_seen_beacon, [data-testid="slider_item"]')
    if not isinstance(payload, dict):
        raise BrowserError("Indeed returned a page we could not read.")
    if payload.get("blocked"):
        raise BrowserError(
            "Indeed served its anti-bot challenge instead of results. There is "
            "no way around that from a headless browser - search the company "
            "boards under greenhouse/lever/ashby instead."
        )

    return to_listings(payload.get("rows") or [])
