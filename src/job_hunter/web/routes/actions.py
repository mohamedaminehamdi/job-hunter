"""Actions: every route that changes something.

Each one does the same three things - read the form, call one library function,
redirect back with a message. Errors are the library's messages, passed to the
page as text; nothing here decides what went wrong.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

import yaml
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, RedirectResponse

from ... import render
from ...config import Settings, load_settings
from ...generate import answers as answers_mod
from ...generate import cover_letter as letter_mod
from ...generate import cv as cv_mod
from ...generate import store as doc_store
from ...generate.errors import GenerationError
from ...generate.llm import LLMError
from ...jobs import parse as job_parse
from ...jobs import store as job_store
from ...jobs.fetch import FetchError
from ...profile import intake
from ...profile import store as profile_store
from ...profile.models import Profile

router = APIRouter()

#: Everything the library raises on purpose; all carry a message for the user.
USER_ERRORS = (
    intake.IntakeError, FetchError, job_parse.ParseError, GenerationError,
    LLMError, render.ExportBlocked, render.PdfError,
)


def _back(path: str, *, error: str = "", note: str = "") -> RedirectResponse:
    """Redirect to a page, carrying one message. 303 so a reload is not a repost."""
    query = urlencode({k: v for k, v in (("error", error), ("note", note)) if v})
    return RedirectResponse(f"{path}?{query}" if query else path, status_code=303)


def _profile(settings: Settings) -> Profile:
    return profile_store.load(profile_store.profile_path(settings.home))


@router.post("/profile/import")
def import_cv(file: Annotated[UploadFile, File()]):
    """Import an uploaded CV. The file is written to a temp path, never kept."""
    settings = load_settings()
    suffix = Path(file.filename or "cv.txt").suffix.lower() or ".txt"
    try:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory) / f"upload{suffix}"
            temporary.write_bytes(file.file.read())
            result = intake.from_file(temporary, settings=settings)
        profile_store.save(result.profile, profile_store.profile_path(settings.home))
    except USER_ERRORS as exc:
        return _back("/", error=str(exc))

    note = "Imported. A model read this CV - check it before you send anything." \
        if result.extracted else "Imported."
    return _back("/profile", note=note)


@router.post("/profile")
def save_profile(yaml_text: Annotated[str, Form()] = ""):
    """Save hand-edited profile YAML."""
    settings = load_settings()
    try:
        raw = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as exc:
        return _back("/profile", error=f"That is not valid YAML: {exc}")
    if not isinstance(raw, dict):
        return _back("/profile", error="The profile must be a mapping at the top level.")

    profile_store.save(profile_store.from_dict(raw),
                       profile_store.profile_path(settings.home))
    return _back("/profile", note="Saved.")


@router.post("/jobs")
def add_job(url: Annotated[str, Form()] = "", text: Annotated[str, Form()] = ""):
    """Add a job from a URL or from pasted description text."""
    settings = load_settings()
    if not url.strip() and not text.strip():
        return _back("/", error="Paste a job URL or the description text.")
    try:
        job = (job_parse.from_text(text, settings=settings) if text.strip()
               else job_parse.from_url(url, settings=settings))
    except USER_ERRORS as exc:
        return _back("/", error=str(exc))

    job_store.save(job, settings.home)
    problem = job.missing()
    return _back(f"/jobs/{job.slug}", error=problem or "", note="" if problem else "Added.")


@router.post("/jobs/{slug}/delete")
def delete_job(slug: str):
    settings = load_settings()
    job_store.delete(slug, settings.home)
    return _back("/", note="Removed.")


@router.post("/jobs/{slug}/cv")
def generate_cv(slug: str):
    settings = load_settings()
    job = job_store.load(slug, settings.home)
    if job is None:
        return _back("/", error=f"No saved job called {slug!r}.")
    try:
        document = cv_mod.tailor(_profile(settings), job, settings=settings)
    except USER_ERRORS as exc:
        return _back(f"/jobs/{slug}", error=str(exc))

    doc_store.save(document, slug, "cv", settings.home)
    return _back(f"/jobs/{slug}/cv", note="Tailored. Read it before you export it.")


@router.post("/jobs/{slug}/letter")
def generate_letter(slug: str):
    settings = load_settings()
    job = job_store.load(slug, settings.home)
    if job is None:
        return _back("/", error=f"No saved job called {slug!r}.")
    try:
        letter = letter_mod.write(_profile(settings), job, settings=settings)
    except USER_ERRORS as exc:
        return _back(f"/jobs/{slug}", error=str(exc))

    doc_store.save(letter, slug, "letter", settings.home)
    return _back(f"/jobs/{slug}/letter", note="Written. Read it before you export it.")


@router.post("/jobs/{slug}/answers")
def draft_answer(slug: str, question: Annotated[str, Form()] = "",
                 words: Annotated[int, Form()] = 150):
    settings = load_settings()
    job = job_store.load(slug, settings.home)
    if job is None:
        return _back("/", error=f"No saved job called {slug!r}.")
    if not question.strip():
        return _back(f"/jobs/{slug}", error="Type the question first.")
    try:
        drafted = answers_mod.answer(_profile(settings), job, question,
                                     words=words, settings=settings)
    except USER_ERRORS as exc:
        return _back(f"/jobs/{slug}", error=str(exc))

    doc_store.add_answer(drafted, slug, settings.home)
    return _back(f"/jobs/{slug}", note="Drafted an answer.")


@router.post("/jobs/{slug}/{kind}/export")
def export_document(slug: str, kind: str, theme: Annotated[str, Form()] = "neutral",
                    branded: Annotated[str, Form()] = ""):
    """Write the PDF. `render.export` refuses if the document is not fit to send."""
    settings = load_settings()
    document = doc_store.load(slug, kind, settings.home) if kind in doc_store.KINDS else None
    if document is None:
        return _back(f"/jobs/{slug}", error="Generate the document first.")

    chosen = render.resolve(theme)
    if branded:
        job = job_store.load(slug, settings.home)
        chosen = render.branded(job.brand_color if job else "", base=chosen)
    try:
        path = render.export(document, settings.output_dir / f"{slug}-{kind}.pdf",
                             theme=chosen)
    except USER_ERRORS as exc:
        return _back(f"/jobs/{slug}/{kind}", error=str(exc))

    return _back(f"/jobs/{slug}/{kind}", note=f"Exported to {path}")


@router.get("/download/{name}")
def download(name: str):
    """Serve a generated PDF.

    Only a plain filename inside the output directory is served: the name is
    reduced to its last path component before it is used, so a crafted path
    cannot walk out of the folder.
    """
    settings = load_settings()
    target = settings.output_dir / Path(name).name
    if target.suffix.lower() != ".pdf" or not target.is_file():
        return _back("/", error="That file is not there.")
    return FileResponse(target, media_type="application/pdf", filename=target.name)
