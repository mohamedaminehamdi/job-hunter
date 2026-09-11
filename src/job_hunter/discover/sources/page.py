"""Any page that lists jobs, read with a browser.

The catch-all, and the answer to "search anything on the internet": a company's
careers page, a board's search results, a jobs newsletter's archive, an ATS
whose slug you do not know. If Chrome renders a list of postings, this turns it
into listings.

It works by finding the links that lead to postings and reading the card each
link sits in. That is a heuristic and a loose one - a page with an odd structure
yields odd titles. Loose is the right setting here: a source that sometimes
over-collects is more useful than one that only understands three boards,
because everything it finds is scored and reviewed before anything happens to it.

The browser returns raw text and this module does the parsing, so the fiddly
half - which line is the title, which is the location - is testable without
launching Chromium.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from ..criteria import Criteria
from ..models import Listing
from .browser import BrowserError, read

#: Link text that is furniture rather than a posting.
_FURNITURE = re.compile(
    r"^(apply( now)?|view( all)?|see all( jobs)?|create( a)? job alert|create alert|"
    r"sign ?in|log ?in|register|back to jobs|load more|show more|next|previous|"
    r"share|save|learn more|read more|all jobs|open roles?|careers?|home)$",
    re.IGNORECASE,
)

#: Paths that live on a job board without being a job.
_NOT_A_POSTING = re.compile(
    r"/(users|login|sign[_-]?in|register|alerts?|privacy|cookies?|terms|about|"
    r"search|blog|news|press|contact)(/|$|\?)",
    re.IGNORECASE,
)

#: "Zurich, Switzerland", "New York, NY", "Remote - EU". What a location looks
#: like when a card puts one on its own line.
#: The capitals are load-bearing in the second branch - they are what stops it
#: matching ordinary prose - so only the "remote" branch ignores case.
_LOOKS_LIKE_PLACE = re.compile(
    r"^((?i:remote\b.*)|[A-Z][\w.'-]*(?:[ -][\w.'-]+){0,3},\s*[A-Z][\w.'-]*"
    r"(?:[ -][\w.'-]+){0,3})$"
)

#: "Financial Partnerships Manager, International" has the shape of a place and
#: is a job title. A fragment naming a role is never a location.
_ROLE_WORD = re.compile(
    r"\b(manager|engineer|director|representative|analyst|lead|specialist|strategist|"
    r"designer|scientist|developer|architect|consultant|associate|intern|officer|"
    r"president|head|counsel|recruiter|partner|advisor|administrator|assistant)\b",
    re.IGNORECASE,
)

#: Cards separate a title from its metadata with these as often as with newlines.
_SEPARATORS = re.compile(r"\s*[•·|]\s*")

_EXTRACT = """
() => {
  const JOB = new RegExp(
    '/(jobs?|careers?|positions?|openings?|vacanc\\\\w*|apply|stellen|emplois)\\\\b' +
    '|greenhouse\\\\.io|lever\\\\.co|ashbyhq\\\\.com|myworkdayjobs|smartrecruiters' +
    '|bamboohr|teamtailor|personio|recruitee|jobvite|icims|workable|breezy\\\\.hr',
    'i');
  const site = document.querySelector('meta[property="og:site_name"]');
  const seen = new Set();
  const out = [];
  for (const a of document.querySelectorAll('a[href]')) {
    const href = a.href;
    if (!href || !href.startsWith('http') || !JOB.test(href)) continue;
    const key = href.split('#')[0];
    if (seen.has(key)) continue;
    seen.add(key);
    const card = a.closest('li, tr, article, [class*="card"], [class*="job"], [class*="post"]')
                 || a.parentElement;
    out.push({
      url: href,
      text: (a.innerText || a.textContent || '').slice(0, 400),
      context: ((card && card.innerText) || '').slice(0, 1200),
      site: (site && site.content) || '',
    });
    if (out.length >= 300) break;
  }
  return out;
}
"""


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def title_of(text: str) -> str:
    """The posting's title out of a link's text.

    A card's link usually wraps the whole card, so its text is the title plus
    the department, the location and the contract type. The title is the first
    line, up to the first separator.
    """
    lines = _lines(text)
    if not lines:
        return ""
    first = _SEPARATORS.split(lines[0])[0].strip()
    return re.sub(r"\s+", " ", first)[:120]


def location_of(text: str, criteria: Criteria) -> str:
    """A location from the card, when the card clearly states one.

    Two ways, both conservative. A place the user asked about, found anywhere in
    the card, is safe to report. Otherwise a line - or a separated fragment -
    that looks like a place. Everything else stays empty, because guessing a
    location wrong is worse for the score than admitting there is none.
    """
    lowered = text.lower()
    for wanted in criteria.locations:
        if (name := wanted.strip()) and name.lower() in lowered:
            return name

    # Everything except the title itself: the rest of the title's own line, on
    # the boards that write "Backend Engineer - Remote - Full time" in one, and
    # every line under it on the boards that use one line per field.
    lines = _lines(text)
    fragments = [part.strip() for part in _SEPARATORS.split(lines[0])[1:]] if lines else []
    fragments += [part.strip() for line in lines[1:] for part in _SEPARATORS.split(line)]
    for fragment in fragments:
        if (len(fragment) <= 60 and _LOOKS_LIKE_PLACE.match(fragment)
                and not _ROLE_WORD.search(fragment)):
            return fragment
    return ""


def _company(site: str, url: str) -> str:
    """Whose board this is: what the page calls itself, else its board slug."""
    if named := site.strip():
        return named
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    parts = [p for p in parsed.path.split("/") if p]
    if host.endswith(("greenhouse.io", "lever.co", "ashbyhq.com")) and parts:
        return parts[0].replace("-", " ").title()
    return host.split(".")[0].replace("-", " ").title()


def _card(link_text: str, context: str) -> str:
    """The text belonging to this posting, and no other.

    Some boards render the whole list inside one element, so `closest()` hands
    back a container holding fifty postings. A location or a summary read out of
    that would describe somebody else's job, so a card that dwarfs its own link
    is discarded and the link's text stands alone.
    """
    if len(context) <= max(400, 4 * len(link_text)):
        return context
    return link_text


def to_listing(row: dict, criteria: Criteria) -> Listing | None:
    """One extracted link as a listing, or None if it is page furniture."""
    url = str(row.get("url", ""))
    if not url or _NOT_A_POSTING.search(urlparse(url).path):
        return None

    title = title_of(str(row.get("text", "")))
    if len(title) < 3 or _FURNITURE.match(title):
        return None

    card = _card(str(row.get("text", "")), str(row.get("context", "")))
    flattened = re.sub(r"\s+", " ", card).strip()
    return Listing(
        url=url,
        title=title,
        company=_company(str(row.get("site", "")), url),
        location=location_of(card, criteria),
        workplace="remote" if "remote" in flattened.lower() else "",
        snippet=flattened[:400],
        source="page",
    )


def search(url: str, criteria: Criteria, *, timeout: int = 30) -> list[Listing]:
    """Every posting linked from one page."""
    rows = read(url, _EXTRACT, timeout=timeout)
    if not isinstance(rows, list):
        raise BrowserError(f"{url} did not look like a page listing jobs.")
    found = [listing for row in rows if isinstance(row, dict)
             if (listing := to_listing(row, criteria)) is not None]
    return found
