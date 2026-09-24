"""A job posting: fetching the page, and modelling what is on it.

Nothing here calls a model. `fetch` gets the text; Claude Code reads it and
writes `job.json`; `models.from_dict` validates that, overriding the URL and
the fetch time with what was actually observed.
"""

from __future__ import annotations

from . import fetch, models
from .fetch import FetchError, PageSource, normalise_url
from .models import Job, from_dict, now

__all__ = ["FetchError", "Job", "PageSource", "fetch", "from_dict", "models",
           "normalise_url", "now"]
