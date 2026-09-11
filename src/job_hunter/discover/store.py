"""The queue: everything a search found, and what you decided about it.

One file, `~/.job-hunter/queue.yaml`, because the queue is read and written as a
whole - a search adds thirty entries at once and the page shows all of them.

The rule that makes repeated searching bearable: **a decision is never
overwritten by a later search.** Dismiss a job today and tomorrow's search will
find it again on three different boards; it stays dismissed, and its listing
data is refreshed underneath the decision.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ..config import load_settings
from .models import Candidate, Listing, Match, now

FILENAME = "queue.yaml"

NEW = "new"
PICKED = "picked"
DISMISSED = "dismissed"
STATUSES = (NEW, PICKED, DISMISSED)


def queue_path(home: Path | None = None) -> Path:
    return (home or load_settings().home) / FILENAME


def load(home: Path | None = None) -> list[Candidate]:
    """Every candidate, best first. Malformed YAML reads as an empty queue."""
    target = queue_path(home)
    if not target.exists():
        return []
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or []
    except yaml.YAMLError:
        return []
    if not isinstance(raw, list):
        return []

    candidates = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            candidates.append(Candidate.model_validate(entry))
        except Exception:
            continue  # one bad entry must not lose the queue
    return rank(candidates)


def save(candidates: list[Candidate], home: Path | None = None) -> Path:
    target = queue_path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump([c.model_dump(mode="json") for c in rank(candidates)],
                       sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    return target


def rank(candidates: list[Candidate]) -> list[Candidate]:
    """Best score first, newest first within a score. Two passes because the
    two keys sort in opposite directions and one is a string."""
    newest = sorted(candidates, key=lambda c: c.listing.found_at, reverse=True)
    return sorted(newest, key=lambda c: -c.match.score)


def merge(existing: list[Candidate], found: list[Candidate]) -> tuple[list[Candidate], int]:
    """Fold a search's results into the queue. Returns the queue and how many
    of the results were new.

    A candidate already in the queue keeps its status and its decision date; its
    listing and score are refreshed, because the board may have edited the
    posting and the profile may have gained a skill since.
    """
    by_id = {c.id: c for c in existing}
    added = 0
    for candidate in found:
        if (seen := by_id.get(candidate.id)) is None:
            by_id[candidate.id] = candidate
            added += 1
            continue
        by_id[candidate.id] = seen.model_copy(update={
            "listing": candidate.listing.model_copy(
                update={"found_at": seen.listing.found_at}),
            "match": candidate.match,
        })
    return rank(list(by_id.values())), added


def get(candidate_id: str, home: Path | None = None) -> Candidate | None:
    return next((c for c in load(home) if c.id == candidate_id), None)


def set_status(candidate_id: str, status: str, home: Path | None = None,
               *, job_slug: str = "") -> Candidate | None:
    """Record a decision. Returns the updated candidate, or None if unknown."""
    if status not in STATUSES:
        return None
    candidates = load(home)
    updated = None
    for index, candidate in enumerate(candidates):
        if candidate.id == candidate_id:
            updated = candidate.model_copy(update={
                "status": status,
                "decided_at": now(),
                "job_slug": job_slug or candidate.job_slug,
            })
            candidates[index] = updated
            break
    if updated is not None:
        save(candidates, home)
    return updated


def waiting(home: Path | None = None) -> list[Candidate]:
    """What still needs a decision from you."""
    return [c for c in load(home) if c.status == NEW]


def counts(home: Path | None = None) -> dict[str, int]:
    """How many are in each state, for the dashboard."""
    candidates = load(home)
    return {status: sum(1 for c in candidates if c.status == status)
            for status in STATUSES} | {"total": len(candidates)}


def clear(home: Path | None = None, *, status: str = "") -> int:
    """Drop candidates - all of them, or just one state. Returns how many went."""
    candidates = load(home)
    kept = [c for c in candidates if c.status != status] if status else []
    save(kept, home)
    return len(candidates) - len(kept)


def candidate_of(listing: Listing, match: Match) -> Candidate:
    return Candidate(listing=listing, match=match)
