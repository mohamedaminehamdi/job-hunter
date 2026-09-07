"""The template environment, and the small helpers the pages need.

Separate from `app.py` so routes can import it without importing the app.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from ..profile.models import Severity

TEMPLATE_DIR = Path(__file__).parent / "templates"

#: How each severity looks in the checklists.
MARKS = {
    Severity.BLOCKING: ("blocking", "must fix"),
    Severity.WARNING: ("warning", "check"),
    Severity.INFO: ("info", "optional"),
}

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env.globals["marks"] = MARKS
