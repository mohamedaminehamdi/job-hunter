"""The source registry: one name, one callable, one kind of transport.

Sources split into two kinds, and the split is what the search planner cares
about. The ATS boards are plain HTTP - fast, safe to run several at once. The
rest need a real browser, which is slow and memory-hungry, so those run one at a
time.
"""

from __future__ import annotations

from collections.abc import Callable

from ..criteria import Criteria
from ..models import Listing
from . import ats, indeed, linkedin, page
from .ats import SourceError
from .browser import BrowserError

#: Anything a source may raise when it simply could not answer. Never fatal:
#: one board being down must not lose the other nineteen.
SOURCE_ERRORS = (SourceError, BrowserError)

#: name -> (callable taking a target, needs a browser)
#: The board sources take a slug; `page` takes a URL; the search engines take
#: nothing and read the criteria instead.
BOARDS: dict[str, Callable[[str], list[Listing]]] = {
    "greenhouse": ats.greenhouse,
    "lever": ats.lever,
    "ashby": ats.ashby,
}

#: The search engines take one location per run: their guest search accepts a
#: single place, and a bare city it cannot resolve lands somewhere else entirely
#: - "Zurich" on LinkedIn returns London, Ontario. One run per location you
#: named is both more thorough and how the mistake stays visible.
ENGINES: dict[str, Callable[..., list[Listing]]] = {
    "linkedin": linkedin.search,
    "indeed": indeed.search,
}

ALL = (*BOARDS, "page", *ENGINES)


def targets(criteria: Criteria) -> dict[str, list[str]]:
    """What each source has been asked to look at, by name."""
    return {
        "greenhouse": list(criteria.greenhouse),
        "lever": list(criteria.lever),
        "ashby": list(criteria.ashby),
        "page": list(criteria.pages),
        "linkedin": (list(criteria.locations) or [""]) if criteria.linkedin else [],
        "indeed": (list(criteria.locations) or [""]) if criteria.indeed else [],
    }


def needs_browser(name: str) -> bool:
    return name not in BOARDS


def run(name: str, target: str, criteria: Criteria, *, timeout: int = 30) -> list[Listing]:
    """Search one source against one target. Raises only `SOURCE_ERRORS`."""
    if name in BOARDS:
        return BOARDS[name](target, timeout=timeout)
    if name == "page":
        return page.search(target, criteria, timeout=timeout)
    if name in ENGINES:
        return ENGINES[name](criteria, where=target, timeout=timeout)
    raise SourceError(f"No such source: {name!r}. Known: {', '.join(ALL)}.")


__all__ = ["ALL", "BOARDS", "ENGINES", "SOURCE_ERRORS", "BrowserError", "SourceError",
           "needs_browser", "run", "targets"]
