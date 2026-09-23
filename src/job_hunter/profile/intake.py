"""Turning whatever the user has into a Profile.

Two kinds of path, kept strictly separate:

* **Deterministic** - YAML in, Profile out. No model, no surprises.
* **Extraction** - a PDF/DOCX/text CV becomes text deterministically, then a
  model maps that text onto the schema.

Extraction is generation, so it can invent just like tailoring can. It therefore
returns the Profile *and* the source text, so the review step can show the user
what the model was looking at.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..generate import parsing
from .models import Profile
from .store import from_dict

SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".yaml", ".yml"}

class IntakeError(RuntimeError):
    """The file could not be read at all."""


@dataclass
class IntakeResult:
    profile: Profile
    #: The text the model saw. Empty for deterministic YAML intake.
    source_text: str = ""
    #: True when a model was involved, so the UI knows to demand review.
    extracted: bool = False


def from_file(path: Path) -> IntakeResult:
    """Load a profile from YAML. A CV in any other format is not a profile yet."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        supported = ", ".join(sorted(SUPPORTED))
        raise IntakeError(f"Unsupported file type {suffix!r}. Supported: {supported}")
    if not path.exists():
        raise IntakeError(f"No such file: {path}")

    if suffix in {".yaml", ".yml"}:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise IntakeError("YAML profile must be a mapping at the top level.")
        return IntakeResult(profile=from_dict(raw))

    # Anything else is a CV, not a profile, and reading one needs judgement.
    # `read_text` gets the words out; Claude Code maps them onto the schema and
    # writes profile.yaml. Splitting it that way is what keeps this module free
    # of a model.
    raise IntakeError(
        f"{path.name} is a CV, not a profile. Run the prep-apply skill, or "
        f"'python -m job_hunter.skill profile --cv {path}' to extract its text."
    )


def read_text(path: Path) -> str:
    """Extract plain text from a CV file. Deterministic - no model involved."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_text(path)
    if suffix == ".docx":
        return _docx_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise IntakeError("Reading PDFs needs pypdf: pip install pypdf") from exc
    try:
        pages = [(p.extract_text() or "") for p in PdfReader(str(path)).pages]
    except Exception as exc:
        raise IntakeError(f"Could not read {path.name} as a PDF: {exc}") from exc
    text = "\n".join(pages).strip()
    if not text:
        raise IntakeError(
            f"{path.name} has no extractable text - it may be a scanned image. "
            "Paste the text directly instead."
        )
    return text


def _docx_text(path: Path) -> str:
    try:
        import docx
    except ImportError as exc:  # pragma: no cover
        raise IntakeError("Reading .docx needs python-docx: pip install python-docx") from exc
    try:
        document = docx.Document(str(path))
    except Exception as exc:
        raise IntakeError(f"Could not read {path.name} as a .docx: {exc}") from exc
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    text = "\n".join(t for t in parts if t.strip()).strip()
    if not text:
        raise IntakeError(f"{path.name} appears to be empty.")
    return text


#: "github.com/ada", "www.ada.dev", "linkedin.com/in/ada" - a host and a path,
#: with the scheme missing.
_BARE_URL = re.compile(r"^(?:www\.)?[\w-]+(?:\.[\w-]+)+(?:/\S*)?$")


def _restore_scheme(profile: Profile) -> Profile:
    """Put back the https:// a printed CV left out.

    `render` strips the scheme so a CV shows "github.com/ada" rather than the
    full URL - which means a CV exported by this tool, printed, and imported
    back comes in bare, and the profile check then complains about three links
    that were right all along. Adding the scheme is not a guess: it is the same
    address, written the way the rest of the tool expects.
    """
    personal = profile.personal
    fixed = {field: f"https://{value}"
             for field in ("github", "linkedin", "website")
             if (value := getattr(personal, field, "").strip())
             and _BARE_URL.match(value)}
    if not fixed:
        return profile
    return profile.model_copy(update={"personal": personal.model_copy(update=fixed)})


def parse_json(raw: str) -> dict:
    """Read the extraction response, reporting failures as intake failures.

    The forgiving part lives in `generate.parsing`; this only re-labels its
    errors so a caller handling intake has one exception type to catch.
    """
    try:
        return parsing.parse_json(raw, hint="Try again, or paste your CV as YAML.")
    except parsing.ParseError as exc:
        raise IntakeError(str(exc)) from exc
