"""Documents to HTML, HTML to PDF, and the rule that guards the door.

Nothing here calls a model. The one piece of policy this package owns is that a
document with a blocking issue - an unfilled placeholder, a missing name - does
not become a file. That promise is in the README, so it is enforced in the one
place every export goes through rather than in each caller.
"""

from __future__ import annotations

from pathlib import Path

from ..profile.models import Issue
from .html import cv_html, environment, letter_html
from .pdf import PdfError, write_pdf
from .themes import CLASSIC, NEUTRAL, THEMES, Theme, branded, resolve


class ExportBlocked(RuntimeError):
    """The document has problems that must be fixed before it becomes a file."""

    def __init__(self, issues: list[Issue]) -> None:
        self.issues = issues
        listed = "\n".join(f"  - {issue.path}: {issue.message}" for issue in issues)
        super().__init__(
            f"This document is not ready to export:\n{listed}\n"
            "Fix these, or edit the document, and try again."
        )


def export(document: object, path: Path, *, theme: Theme = NEUTRAL) -> Path:
    """Write a CV or a cover letter to `path` as a PDF.

    Raises `ExportBlocked` if the document reports a blocking issue - which is
    how "nothing becomes a PDF until it is fit to send" is actually kept.
    """
    if blocking := list(getattr(document, "blocking", []) or []):
        raise ExportBlocked(blocking)
    return write_pdf(to_html(document, theme=theme), Path(path))


def to_html(document: object, *, theme: Theme = NEUTRAL) -> str:
    """Render whichever kind of document this is."""
    if hasattr(document, "paragraphs"):
        return letter_html(document, theme=theme)  # type: ignore[arg-type]
    return cv_html(document, theme=theme)  # type: ignore[arg-type]


__all__ = [
    "export", "to_html", "cv_html", "letter_html", "write_pdf", "environment",
    "Theme", "NEUTRAL", "CLASSIC", "THEMES", "branded", "resolve",
    "ExportBlocked", "PdfError",
]
