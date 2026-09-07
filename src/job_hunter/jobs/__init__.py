"""A job posting: fetching one, and what one is.

Knows nothing about the profile - `generate/` is where the two meet.
"""

from . import fetch as fetch_module
from . import models, parse
from .fetch import FetchError, PageSource, normalise_url
from .fetch import fetch as fetch_page
from .models import Job
from .parse import ParseError, from_text, from_url

__all__ = [
    "Job",
    "models",
    "parse",
    "from_url",
    "from_text",
    "fetch_page",
    "fetch_module",
    "normalise_url",
    "PageSource",
    "FetchError",
    "ParseError",
]
