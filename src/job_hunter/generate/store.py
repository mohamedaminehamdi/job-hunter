"""Saving generated documents as YAML.

Under ``~/.job-hunter/documents/``, keyed by the job slug, because the review
step and the export step are separate HTTP requests and the document has to
survive between them. YAML, not a database: a generated CV is a thing the user
should be able to open and edit before it becomes a PDF.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from ..config import load_settings
from .answers import Answer
from .cover_letter import CoverLetter
from .cv import TailoredCV

DIRNAME = "documents"

#: Suffix -> model, so one pair of functions serves every document kind.
KINDS: dict[str, type[BaseModel]] = {"cv": TailoredCV, "letter": CoverLetter}


def documents_dir(home: Path | None = None) -> Path:
    return (home or load_settings().home) / DIRNAME


def document_path(slug: str, kind: str, home: Path | None = None) -> Path:
    return documents_dir(home) / f"{slug}-{kind}.yaml"


def save(document: BaseModel, slug: str, kind: str, home: Path | None = None) -> Path:
    target = document_path(slug, kind, home)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(document.model_dump(mode="json"), sort_keys=False,
                       allow_unicode=True, width=100),
        encoding="utf-8",
    )
    return target


def load(slug: str, kind: str, home: Path | None = None) -> BaseModel | None:
    """One document, or None if it is absent or unreadable."""
    model = KINDS.get(kind)
    target = document_path(slug, kind, home)
    if model is None or not target.exists():
        return None
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        return model.model_validate(raw) if isinstance(raw, dict) else None
    except Exception:
        return None


def save_answers(answers: list[Answer], slug: str, home: Path | None = None) -> Path:
    """All answers for one job in one file - a form has many questions."""
    target = document_path(slug, "answers", home)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump([a.model_dump(mode="json") for a in answers], sort_keys=False,
                       allow_unicode=True, width=100),
        encoding="utf-8",
    )
    return target


def load_answers(slug: str, home: Path | None = None) -> list[Answer]:
    target = document_path(slug, "answers", home)
    if not target.exists():
        return []
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or []
    except yaml.YAMLError:
        return []
    if not isinstance(raw, list):
        return []
    found: list[Answer] = []
    for item in raw:
        try:
            found.append(Answer.model_validate(item))
        except Exception:
            continue
    return found


def add_answer(answer: Answer, slug: str, home: Path | None = None) -> Path:
    """Append one answer, replacing any earlier answer to the same question."""
    kept = [a for a in load_answers(slug, home) if a.question != answer.question]
    return save_answers([*kept, answer], slug, home)
