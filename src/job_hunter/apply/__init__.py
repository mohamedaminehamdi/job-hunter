"""Recording what you actually sent.

The last step, and the only one that produces something no command can rebuild:

    pick -> tailor -> export -> applied -> mark interviewing / rejected
                                   |
                        applications/<slug>.yaml

It is deliberately a leaf. It reads no documents, calls no model and renders
nothing; `record()` takes a job object rather than importing `jobs`. All it
knows is that you sent something on a date, and what has happened since.
"""

from __future__ import annotations

from .models import (
    APPLIED,
    FOLLOW_UP_DAYS,
    INTERVIEWING,
    NEXT,
    OFFER,
    OPEN,
    REJECTED,
    SENT_KINDS,
    STATES,
    WITHDRAWN,
    Application,
    ApplyError,
    Event,
    today,
)

__all__ = ["APPLIED", "FOLLOW_UP_DAYS", "INTERVIEWING", "NEXT", "OFFER", "OPEN",
           "REJECTED", "SENT_KINDS", "STATES", "WITHDRAWN", "Application",
           "ApplyError", "Event", "today"]
