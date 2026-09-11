"""Saving applications as YAML, one file per job slug.

Under ``~/.job-hunter/applications/<slug>.yaml``, beside the job it belongs to
and the documents generated for it. One file rather than one list, for the
reason `jobs/store.py` uses one: a bad line costs that record and not the set,
and "what did I send to Acme" is a file you can open.

Nothing here raises on load. `mark` and `add_note` return None when there is
nothing to change or the move is illegal; the caller turns that into a message,
the same contract as `discover.store.set_status`.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ..config import load_settings
from .models import (
    APPLIED,
    FOLLOW_UP_DAYS,
    NEXT,
    OPEN,
    STATES,
    Application,
    Event,
    from_dict,
    now,
    today,
)

DIRNAME = "applications"


def applications_dir(home: Path | None = None) -> Path:
    return (home or load_settings().home) / DIRNAME


def application_path(slug: str, home: Path | None = None) -> Path:
    return applications_dir(home) / f"{slug}.yaml"


def save(application: Application, home: Path | None = None) -> Path:
    target = application_path(application.job_slug, home)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(application.model_dump(mode="json"), sort_keys=False,
                       allow_unicode=True, width=100),
        encoding="utf-8",
    )
    return target


def load(slug: str, home: Path | None = None) -> Application | None:
    """One application by slug, or None. Malformed YAML reads as missing."""
    target = application_path(slug, home)
    if not target.exists():
        return None
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    return from_dict(raw) if isinstance(raw, dict) else None


def all_applications(home: Path | None = None) -> list[Application]:
    """Every application, most recently sent first."""
    directory = applications_dir(home)
    if not directory.is_dir():
        return []
    found = [a for path in sorted(directory.glob("*.yaml"))
             if (a := load(path.stem, home)) is not None]
    return sorted(found, key=lambda a: a.applied_on, reverse=True)


def delete(slug: str, home: Path | None = None) -> bool:
    target = application_path(slug, home)
    if not target.exists():
        return False
    target.unlink()
    return True


def record(job, *, on: str = "", channel: str = "", sent: list[str] | None = None,
           contact: str = "", note: str = "", home: Path | None = None) -> Application:
    """Record that you applied to `job`.

    Takes the job rather than importing `jobs.models`, which keeps this package
    a leaf. Company, role and URL are copied now so the record outlives the
    posting. Recording twice updates the details and leaves the state alone -
    you do not un-interview by correcting the channel.
    """
    existing = load(job.slug, home)
    applied_on = on.strip() or (existing.applied_on if existing else "") or today()

    if existing is None:
        application = Application(
            job_slug=job.slug, company=job.company, role=job.title, url=job.url,
            status=APPLIED, applied_on=applied_on, channel=channel.strip(),
            sent=list(sent or []), contact=contact.strip(),
            history=[Event(at=applied_on, status=APPLIED, note=note.strip())],
        )
    else:
        application = existing.model_copy(update={
            "applied_on": applied_on,
            "channel": channel.strip() or existing.channel,
            "sent": list(sent) if sent else existing.sent,
            "contact": contact.strip() or existing.contact,
            "history": ([*existing.history, Event(status="", note=note.strip())]
                        if note.strip() else existing.history),
        })
    save(application, home)
    return application


def mark(slug: str, status: str, *, on: str = "", note: str = "",
         home: Path | None = None) -> Application | None:
    """Move an application to `status`. None if unknown, or the move is illegal."""
    application = load(slug, home)
    if application is None or status not in STATES:
        return None
    if status not in application.next_states:
        return None

    moved = application.model_copy(update={
        "status": status,
        "history": [*application.history,
                    Event(at=on.strip() or now(), status=status, note=note.strip())],
    })
    save(moved, home)
    return moved


def add_note(slug: str, note: str, home: Path | None = None) -> Application | None:
    """Add a dated note. Resets the quiet clock, which is the point of it."""
    application = load(slug, home)
    if application is None or not note.strip():
        return None
    noted = application.model_copy(update={
        "history": [*application.history, Event(status="", note=note.strip())],
    })
    save(noted, home)
    return noted


def outstanding(home: Path | None = None,
                *, quiet_for: int = FOLLOW_UP_DAYS) -> list[Application]:
    """Open applications nobody has moved in a while, longest wait first."""
    quiet = [a for a in all_applications(home) if a.is_quiet(quiet_for)]
    return sorted(quiet, key=lambda a: a.days_quiet or 0, reverse=True)


def counts(home: Path | None = None) -> dict[str, int]:
    """How many are in each state, plus the two numbers worth a glance."""
    found = all_applications(home)
    tally = {state: sum(1 for a in found if a.status == state) for state in STATES}
    return tally | {
        "open": sum(1 for a in found if a.is_open),
        "quiet": sum(1 for a in found if a.is_quiet()),
        "total": len(found),
    }


def legal_moves(status: str) -> tuple[str, ...]:
    return NEXT.get(status, ())


__all__ = ["DIRNAME", "OPEN", "add_note", "all_applications", "application_path",
           "applications_dir", "counts", "delete", "legal_moves", "load", "mark",
           "outstanding", "record", "save"]
