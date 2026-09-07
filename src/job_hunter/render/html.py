"""Documents to HTML.

The Jinja environment lives here with autoescaping on: everything rendered is
either the user's own text or a model's output, and both reach the page as data.
No model is called in this package - by the time a document arrives here every
decision about its content has been made.
"""

from __future__ import annotations

from datetime import date

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from ..generate.cover_letter import CoverLetter
from ..profile.models import Profile
from .themes import NEUTRAL, Theme


def _strip_scheme(url: str) -> str:
    """Show 'github.com/ada', not 'https://github.com/ada' - it is a printed page."""
    return str(url).removeprefix("https://").removeprefix("http://").rstrip("/")


def _long_date(value: str) -> str:
    """An ISO date as '7 September 2026'. Anything else passes through."""
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError:
        return str(value)
    return f"{parsed.day} {parsed.strftime('%B %Y')}"


def environment() -> Environment:
    env = Environment(
        loader=PackageLoader("job_hunter.render", "templates"),
        autoescape=select_autoescape(["html", "j2"], default_for_string=True),
        # A template referring to a field that does not exist should fail loudly
        # here, not print the word "Undefined" into somebody's CV.
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["strip_scheme"] = _strip_scheme
    env.filters["long_date"] = _long_date
    return env


def cv_html(document: Profile, *, theme: Theme = NEUTRAL) -> str:
    """A CV (or a plain profile) as a self-contained HTML page."""
    title = getattr(document, "job_label", "") or document.personal.full_name or "CV"
    return environment().get_template("cv.html.j2").render(
        doc=document, theme=theme, title=f"CV - {title}",
    )


def letter_html(letter: CoverLetter, *, theme: Theme = NEUTRAL) -> str:
    """A cover letter as a self-contained HTML page."""
    who = letter.personal.full_name or "Cover letter"
    return environment().get_template("cover_letter.html.j2").render(
        letter=letter, theme=theme,
        title=f"Cover letter - {letter.company or who}",
    )
