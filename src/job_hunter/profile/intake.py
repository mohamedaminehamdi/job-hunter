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

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..generate import llm
from .models import Profile
from .store import from_dict

SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".yaml", ".yml"}

_SYSTEM = """You extract structured data from CVs.

Rules:
- Copy facts verbatim wherever possible. Do not rephrase achievements.
- Never invent. If a field is absent from the CV, leave it empty.
- Do not add courses, skills, dates or employers that are not written in the text.
- Return only JSON matching the requested shape. No prose, no code fences."""

_SHAPE = """{
  "personal": {"name":"","surname":"","headline":"","email":"","phone":"",
               "city":"","country":"","github":"","linkedin":"","website":""},
  "summary": "",
  "experience": [{"position":"","company":"","start":"","end":"","location":"",
                  "industry":"","bullets":[""],"skills":[""]}],
  "education": [{"level":"","institution":"","field_of_study":"","start":"",
                 "end":"","grade":"","location":"","courses":[""]}],
  "projects": [{"name":"","description":"","link":"","tech":[""]}],
  "skills": [""],
  "certifications": [{"name":"","issuer":"","year":"","description":""}],
  "languages": [{"name":"","level":""}]
}"""


class IntakeError(RuntimeError):
    """The file could not be read at all."""


@dataclass
class IntakeResult:
    profile: Profile
    #: The text the model saw. Empty for deterministic YAML intake.
    source_text: str = ""
    #: True when a model was involved, so the UI knows to demand review.
    extracted: bool = False


def from_file(path: Path, **kwargs) -> IntakeResult:
    """Load a profile from any supported file type."""
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

    return from_text(read_text(path), **kwargs)


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


def from_text(text: str, *, settings=None) -> IntakeResult:
    """Map free-text CV content onto the schema using a model."""
    if not text.strip():
        raise IntakeError("Nothing to extract from - the text is empty.")

    prompt = (
        f"Extract this CV into exactly this JSON shape:\n\n{_SHAPE}\n\n"
        "Omit any array entry you would otherwise fill with empty strings.\n\n"
        f"CV:\n---\n{text}\n---"
    )
    result = llm.complete(prompt, system=_SYSTEM, settings=settings)
    data = parse_json(result.text)
    return IntakeResult(profile=from_dict(data), source_text=text, extracted=True)


def parse_json(raw: str) -> dict:
    """Pull a JSON object out of a model response.

    Models wrap JSON in fences or prose despite instructions, so this is
    forgiving by design rather than trusting the format.
    """
    fence = r"^\s*```(?:json)?|```\s*$"
    cleaned = re.sub(fence, "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1:
            raise IntakeError(
                "The model did not return JSON. Try again, or paste your CV as YAML."
            ) from None
        if end <= start:
            # An object was started but never closed - usually a truncated response.
            raise IntakeError(
                "The model returned malformed JSON (the response looks cut off). "
                "Try again, or paste your CV as YAML."
            ) from None
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise IntakeError(f"The model returned malformed JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise IntakeError("Expected a JSON object describing the profile.")
    return parsed
