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


#: Month names for the languages the tool writes in. `strftime` would follow the
#: machine's locale, which has nothing to do with the posting's language.
_MONTHS = {
    "en": ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"),
    "fr": ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"),
}

#: What a letter calls the line naming the job. French business letters use
#: "Objet :", with the space before the colon that French typography wants.
_SUBJECT = {"en": "Application:", "fr": "Objet :"}


def _key(language: str) -> str:
    """The language to render in. Anything we have no words for reads as English."""
    code = (language or "").strip().lower()[:2]
    return code if code in _MONTHS else "en"


def _long_date(value: str, language: str = "") -> str:
    """An ISO date as '7 September 2026', or '7 septembre 2026'.

    Anything that is not an ISO date passes through untouched.
    """
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError:
        return str(value)
    code = _key(language)
    day = "1er" if parsed.day == 1 and code == "fr" else str(parsed.day)
    return f"{day} {_MONTHS[code][parsed.month - 1]} {parsed.year}"


def _subject(language: str = "") -> str:
    return _SUBJECT[_key(language)]


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
    env.filters["subject_label"] = _subject
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
