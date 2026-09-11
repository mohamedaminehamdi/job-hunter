"""Finding jobs worth applying to, and queueing them for you to decide on.

The half of the tool that runs before `jobs`: search several sources, score
every hit against the profile, and put what survives in a queue. Nothing here
calls a model and nothing here applies to anything. Picking a candidate hands it
to `jobs.parse`, and from there it is an ordinary saved job.

The pipeline, once:

    criteria + profile -> sources.run() -> Listing -> match.score() -> Candidate
                                                                          |
                                                       store.merge() -> queue.yaml

Two design rules hold it together. **Sources fail alone**: a dead board slug or
a sign-in wall is recorded against that source and the search carries on.
**Decisions outlive searches**: a candidate you dismissed stays dismissed when
tomorrow's search finds it again on a different board.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pydantic import BaseModel, Field

from ..profile.models import Profile
from . import match as match_mod
from . import sources, store
from .criteria import Criteria
from .models import Candidate, Listing, Match, now

#: HTTP board requests are cheap and independent, so they overlap. Browser
#: sources are not in here on purpose: each one launches its own Chromium.
MAX_PARALLEL_BOARDS = 8


class SourceOutcome(BaseModel):
    """What one source did when asked. `error` and `found` are exclusive."""

    source: str
    target: str = ""
    found: int = 0
    error: str = ""

    @property
    def label(self) -> str:
        return f"{self.source}:{self.target}" if self.target else self.source


class SearchReport(BaseModel):
    """What a search did, in the numbers a person actually asks about."""

    outcomes: list[SourceOutcome] = Field(default_factory=list)
    #: Unique listings seen across every source.
    found: int = 0
    #: Ruled out by a blacklist or a filter, before scoring.
    excluded: int = 0
    #: Scored, but under `min_score`.
    below: int = 0
    #: Reached the queue.
    queued: int = 0
    #: Of those, never seen before.
    added: int = 0
    at: str = Field(default_factory=now)

    @property
    def errors(self) -> list[SourceOutcome]:
        return [o for o in self.outcomes if o.error]

    def summary(self) -> str:
        """One line, for the CLI and the web flash."""
        parts = [f"{self.found} found", f"{self.queued} queued", f"{self.added} new"]
        if self.excluded:
            parts.append(f"{self.excluded} filtered out")
        if self.below:
            parts.append(f"{self.below} below score")
        if self.errors:
            parts.append(f"{len(self.errors)} source(s) failed")
        return ", ".join(parts) + "."


def _plan(criteria: Criteria, only: tuple[str, ...]) -> list[tuple[str, str]]:
    """Every (source, target) pair this search will run, in a stable order."""
    wanted = set(only) if only else None
    return [(name, target)
            for name, targets in sources.targets(criteria).items()
            if wanted is None or name in wanted
            for target in targets]


def collect(criteria: Criteria, *, timeout: int = 30,
            only: tuple[str, ...] = ()) -> tuple[list[Listing], list[SourceOutcome]]:
    """Run every enabled source. Returns the listings and what each source did.

    Never raises for a source that failed - that is what `SourceOutcome.error`
    is for. A search across twenty boards where one is down is a successful
    search with a note attached.
    """
    plan = _plan(criteria, only)
    fast = [item for item in plan if not sources.needs_browser(item[0])]
    slow = [item for item in plan if sources.needs_browser(item[0])]

    def attempt(item: tuple[str, str]) -> tuple[SourceOutcome, list[Listing]]:
        name, target = item
        try:
            found = sources.run(name, target, criteria, timeout=timeout)
        except sources.SOURCE_ERRORS as exc:
            return SourceOutcome(source=name, target=target, error=str(exc)), []
        except Exception as exc:  # an adapter bug must not lose the whole search
            return SourceOutcome(source=name, target=target,
                                 error=f"{type(exc).__name__}: {exc}"), []
        capped = found[:criteria.limit_per_source]
        return SourceOutcome(source=name, target=target, found=len(capped)), capped

    results: list[tuple[SourceOutcome, list[Listing]]] = []
    if fast:
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_BOARDS, len(fast))) as pool:
            results.extend(pool.map(attempt, fast))
    results.extend(attempt(item) for item in slow)

    listings: list[Listing] = []
    seen: set[str] = set()
    for _, found in results:
        for listing in found:
            if listing.id not in seen:
                seen.add(listing.id)
                listings.append(listing)
    return listings, [outcome for outcome, _ in results]


def rate(listings: list[Listing], profile: Profile,
         criteria: Criteria) -> tuple[list[Candidate], int, int]:
    """Score listings, keeping the ones worth a decision.

    Returns the keepers, how many were excluded outright, and how many merely
    scored too low - the two are different answers and the report says which.
    """
    keepers: list[Candidate] = []
    excluded = below = 0
    for listing in listings:
        result: Match = match_mod.score(listing, profile, criteria)
        if result.is_excluded:
            excluded += 1
        elif result.score < criteria.min_score:
            below += 1
        else:
            keepers.append(Candidate(listing=listing, match=result))
    return keepers, excluded, below


def search(profile: Profile, criteria: Criteria, home: Path | None = None, *,
           timeout: int = 30, only: tuple[str, ...] = ()) -> SearchReport:
    """The whole discovery pass: search, score, queue. Saves and reports."""
    listings, outcomes = collect(criteria, timeout=timeout, only=only)
    keepers, excluded, below = rate(listings, profile, criteria)
    queue, added = store.merge(store.load(home), keepers)
    store.save(queue, home)

    return SearchReport(outcomes=outcomes, found=len(listings), excluded=excluded,
                        below=below, queued=len(keepers), added=added)


__all__ = ["Criteria", "SearchReport", "SourceOutcome", "collect", "rate", "search",
           "sources", "store"]
