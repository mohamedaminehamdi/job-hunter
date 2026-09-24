"""Documents to HTML, HTML to PDF, and the rule that guards the door.

Nothing here calls a model. The one piece of policy this package owns is that a
document with a blocking issue - an unfilled placeholder, a missing name - does
not become a file. That promise is in the README, so it is enforced in the one
place every export goes through rather than in each caller.
"""

from __future__ import annotations

from pathlib import Path

from ..profile.models import Issue, Severity
from .html import cv_html, environment, letter_html
from .markdown import cv_markdown, letter_markdown
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
    if blocking := blocking_issues(document):
        raise ExportBlocked(blocking)
    return write_pdf(to_html(document, theme=theme), Path(path))


def blocking_issues(document: object) -> list[Issue]:
    """What stops this document becoming a file.

    A tailored CV and a letter each publish their own `blocking` list. A plain
    `Profile` publishes none, and would otherwise walk through the door
    unchecked - carrying the '[Your Name]' this whole rule exists to stop - so
    it is validated here instead. The door is one place, for every document.
    """
    if (declared := getattr(document, "blocking", None)) is not None:
        return list(declared)
    report = getattr(document, "report", None)
    found = report() if callable(report) else []
    return [issue for issue in found if issue.severity == Severity.BLOCKING]


def to_markdown(document: object) -> str:
    """Whichever kind of document this is, as markdown.

    Always written before the PDF is attempted, so a machine with no browser
    still gets a document a person can read and send.
    """
    if hasattr(document, "paragraphs"):
        return letter_markdown(document)  # type: ignore[arg-type]
    return cv_markdown(document)  # type: ignore[arg-type]


def to_html(document: object, *, theme: Theme = NEUTRAL) -> str:
    """Render whichever kind of document this is."""
    if hasattr(document, "paragraphs"):
        return letter_html(document, theme=theme)  # type: ignore[arg-type]
    return cv_html(document, theme=theme)  # type: ignore[arg-type]


__all__ = [
    "export", "to_html", "to_markdown", "blocking_issues", "cv_markdown",
    "letter_markdown", "cv_html", "letter_html", "write_pdf", "environment",
    "Theme", "NEUTRAL", "CLASSIC", "THEMES", "branded", "resolve",
    "ExportBlocked", "PdfError",
]
