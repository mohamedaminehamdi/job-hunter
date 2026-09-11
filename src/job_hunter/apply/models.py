"""What you sent, when, and what came back.

The one thing in this tool that cannot be regenerated. A queue can be rebuilt by
searching again, a job by re-fetching it, a CV by re-tailoring - but nothing can
reconstruct the fact that you applied to Thales on the 3rd and never heard back.
That asymmetry is why applications are their own package with their own files,
rather than another state on a queue entry that a "Clear everything" button
truncates.

Two states that look similar are kept apart on purpose: `dismissed` on a queue
candidate means *you* passed on them, `rejected` here means *they* passed on you.
A job hunt is largely the business of telling those two apart.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from pydantic import BaseModel, Field

#: Two weeks is the honest floor for "they have not replied": most automated
#: acknowledgements land within days, and chasing sooner just annoys.
FOLLOW_UP_DAYS = 14

APPLIED = "applied"
INTERVIEWING = "interviewing"
OFFER = "offer"
REJECTED = "rejected"
WITHDRAWN = "withdrawn"

STATES = (APPLIED, INTERVIEWING, OFFER, REJECTED, WITHDRAWN)
#: Still in play, and therefore still worth chasing.
OPEN = (APPLIED, INTERVIEWING, OFFER)

#: Where each state may go. The single source of truth: it validates a move and
#: it fills the web's dropdown, so the UI cannot offer something the store will
#: refuse. Rejected and withdrawn are terminal - re-opening one is a job for
#: your editor, which the error message says.
NEXT: dict[str, tuple[str, ...]] = {
    APPLIED: (INTERVIEWING, OFFER, REJECTED, WITHDRAWN),
    INTERVIEWING: (OFFER, REJECTED, WITHDRAWN),
    OFFER: (REJECTED, WITHDRAWN),  # rescinded, or you turned it down
    REJECTED: (),
    WITHDRAWN: (),
}

#: Document kinds that can be sent with an application. Mirrors
#: `generate.store.KINDS` without importing it - this package stays a leaf.
SENT_KINDS = ("cv", "letter")

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ApplyError(RuntimeError):
    """A move that cannot be made. Carries what to do instead."""


def now() -> str:
    """Timestamp for an event, in the shape every other store uses."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def today() -> str:
    """The date an application is sent. A date, not a timestamp: nobody cares
    about the hour, and this is the field people hand-edit."""
    return datetime.now(UTC).date().isoformat()


def is_slug(value: str) -> bool:
    """Whether this is a job slug and not a path. Callers take it from a URL."""
    return bool(_SLUG.match(value or ""))


class Event(BaseModel):
    """One thing that happened, and when."""

    at: str = Field(default_factory=now)
    #: The state this moved to, or empty for a note that changed nothing.
    status: str = ""
    note: str = ""


class Application(BaseModel):
    """One application: what you sent, when, and what came back."""

    job_slug: str = ""
    #: Copied off the job when you apply, so the record survives the posting
    #: being deleted or re-fetched under a different slug.
    company: str = ""
    role: str = ""
    url: str = ""

    status: str = APPLIED
    applied_on: str = ""
    #: How it went out. Free text on purpose - an enum would be wrong within a
    #: week (a referral, a recruiter's DM, a friend forwarding it on).
    channel: str = ""
    #: Document kinds, not paths. A path into output/ goes stale on the next
    #: export; the kind does not. Note this records what you say you sent, and
    #: the PDF on disk may since have been regenerated.
    sent: list[str] = Field(default_factory=list)
    #: One line. Not a contact record - anything longer is a note.
    contact: str = ""
    #: Every move and every note, oldest first.
    history: list[Event] = Field(default_factory=list)

    @property
    def label(self) -> str:
        if self.role and self.company:
            return f"{self.role} at {self.company}"
        return self.role or self.company or self.job_slug or "Untitled application"

    @property
    def is_open(self) -> bool:
        return self.status in OPEN

    @property
    def next_states(self) -> tuple[str, ...]:
        return NEXT.get(self.status, ())

    @property
    def last_at(self) -> str:
        """When something last happened on this application."""
        return self.history[-1].at if self.history else self.applied_on

    @property
    def days_quiet(self) -> int | None:
        """Days since anything happened, or None when the date is unreadable.

        Counted from the last event rather than from `applied_on`, so chasing
        them resets the clock and the tool stops nagging.
        """
        if not (stamp := self.last_at):
            return None
        try:
            last = date.fromisoformat(str(stamp)[:10])
        except ValueError:
            return None
        return max((datetime.now(UTC).date() - last).days, 0)

    def is_quiet(self, after_days: int = FOLLOW_UP_DAYS) -> bool:
        """Open, and nothing has happened for a while.

        An unreadable date is never quiet - an unknown date is not an old one,
        the same rule the rest of the tool follows.
        """
        quiet = self.days_quiet
        return self.is_open and quiet is not None and quiet >= after_days


def from_dict(raw: dict) -> Application:
    """Build an application from loose YAML, salvaging what parses.

    Hand-editing is the escape hatch for every rule in this package, so one bad
    line must cost that line and not the record.
    """
    known = {k: v for k, v in raw.items() if k in Application.model_fields}
    # PyYAML turns an unquoted 2026-08-24 into a date object; the model wants
    # the string the user typed.
    for field in ("applied_on",):
        if isinstance(known.get(field), (date, datetime)):
            known[field] = known[field].isoformat()[:10]
    try:
        return Application.model_validate(known)
    except Exception:
        application = Application()
        for key, value in known.items():
            try:
                validated = Application.model_validate({key: value})
                application = application.model_copy(
                    update={key: getattr(validated, key)})
            except Exception:
                continue
        return application
