"""Building the LinkedIn searches a person then runs themselves.

No scraping. LinkedIn walls and throttles automated access - we measured it
repeatedly, and the risk of working around that lands on the friend's own
account, not on this repo. So the tool does the part it can do honestly: work
out who is worth contacting, hand over a search that finds them, and draft what
to say.

**Claude never writes a URL.** It names a job title; these functions build the
link. Same structural rule as the rest of the tool: a malformed or hostile URL
cannot be expressed because there is no field for one.
"""

from __future__ import annotations

import re
from urllib.parse import urlencode

PEOPLE = "https://www.linkedin.com/search/results/people/"
COMPANY = "https://www.linkedin.com/company/{slug}/people/"

#: A company's own LinkedIn link, as it appears in a posting's footer.
_SLUG = re.compile(r"linkedin\.com/company/([A-Za-z0-9\-_.]+)", re.IGNORECASE)


def _query(**params: str) -> str:
    return urlencode({k: v for k, v in params.items() if v})


def people_search(title: str, company: str, *, extra: str = "") -> str:
    """Find people with a job title at a company.

    The reliable one: it works for anyone signed in, and it is the same search
    a person would type by hand.
    """
    keywords = " ".join(part for part in (f'"{title}"' if title else "",
                                          company, extra) if part).strip()
    return f"{PEOPLE}?{_query(keywords=keywords)}"


def alumni_search(school: str, company: str) -> str:
    """Find people from the same school who work there.

    Keywords only. The proper alumni filter needs LinkedIn's internal school
    ids, which are not obtainable without scraping, so this is a keyword search
    that usually works rather than a facet that quietly does not.
    """
    return f"{PEOPLE}?{_query(keywords=' '.join(x for x in (school, company) if x))}"


def company_slug(text: str) -> str:
    """The company's LinkedIn slug, if the posting happened to carry it.

    Read out of the page rather than looked up: postings routinely link their
    own LinkedIn in the footer, and a regex over text we already have beats one
    more request that can be blocked.
    """
    match = _SLUG.search(text or "")
    return match.group(1) if match else ""


def company_people(slug: str, *, keywords: str = "") -> str:
    """People at one company, when the posting told us its slug."""
    return f"{COMPANY.format(slug=slug)}?{_query(keywords=keywords)}" if slug else ""
