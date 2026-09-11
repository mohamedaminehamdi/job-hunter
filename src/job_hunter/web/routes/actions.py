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
from ...apply import models as apply_models
from ...apply import store as apply_store
from ...config import Settings, load_settings
from ...discover import criteria as criteria_mod
from ...discover import search as run_search
from ...discover import store as queue_store
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
    LLMError, render.ExportBlocked, render.PdfError, apply_models.ApplyError,
)


def _own_path(path: str, fallback: str = "/applications") -> str:
    """A redirect target this app owns.

    `back` arrives from a form, and a Location header built from form input is
    an open redirect the moment it can carry a scheme or a host.
    """
    return path if path.startswith("/") and not path.startswith("//") else fallback


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


@router.post("/search/criteria")
def save_criteria(yaml_text: Annotated[str, Form()] = ""):
    """Save the hand-edited search YAML. Same contract as the profile editor."""
    settings = load_settings()
    try:
        raw = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as exc:
        return _back("/queue", error=f"That is not valid YAML: {exc}")
    if not isinstance(raw, dict):
        return _back("/queue", error="The search must be a mapping at the top level.")

    criteria_mod.save(criteria_mod.from_dict(raw), settings.home)
    return _back("/queue", note="Saved.")


@router.post("/search")
def search(source: Annotated[str, Form()] = ""):
    """Run every configured source and queue what scores well enough.

    Synchronous, like every other action here: a search over a handful of boards
    is seconds, and a background job would need a status page nobody asked for.
    Turning on LinkedIn or a long list of pages makes it a browser run per
    source, so it can take a minute.
    """
    settings = load_settings()
    criteria = criteria_mod.load(settings.home)
    if not criteria.is_searchable:
        blocking = "; ".join(i.message for i in criteria.report())
        return _back("/queue", error=f"The search is not ready. {blocking}")

    try:
        report = run_search(_profile(settings), criteria, settings.home,
                            only=(source,) if source else ())
    except USER_ERRORS as exc:
        return _back("/queue", error=str(exc))

    failed = "; ".join(f"{o.label}: {o.error}" for o in report.errors)
    return _back("/queue", note=report.summary(), error=failed)


@router.post("/queue/{candidate_id}/pick")
def pick(candidate_id: str):
    """Fetch and parse the posting behind a queued listing, then open it."""
    settings = load_settings()
    candidate = queue_store.get(candidate_id, settings.home)
    if candidate is None:
        return _back("/queue", error="That listing is no longer in the queue.")

    try:
        job = job_parse.from_url(candidate.listing.url, settings=settings)
    except USER_ERRORS as exc:
        return _back("/queue", error=f"{candidate.listing.label}: {exc}")

    job_store.save(job, settings.home)
    queue_store.set_status(candidate_id, queue_store.PICKED, settings.home,
                           job_slug=job.slug)
    return _back(f"/jobs/{job.slug}", note="Picked from the queue.",
                 error=job.missing() or "")


@router.post("/queue/{candidate_id}/dismiss")
def dismiss(candidate_id: str):
    settings = load_settings()
    if queue_store.set_status(candidate_id, queue_store.DISMISSED, settings.home) is None:
        return _back("/queue", error="That listing is no longer in the queue.")
    return _back("/queue", note="Dismissed. Later searches will not bring it back.")


@router.post("/queue/clear")
def clear_queue(status: Annotated[str, Form()] = ""):
    """Empty the queue, or just one state of it."""
    settings = load_settings()
    gone = queue_store.clear(settings.home, status=status)
    return _back("/queue", note=f"Cleared {gone} listing(s).")


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


@router.post("/jobs/{slug}/applied")
def mark_applied(slug: str, on: Annotated[str, Form()] = "",
                 channel: Annotated[str, Form()] = "",
                 sent: Annotated[list[str], Form()] = (),
                 contact: Annotated[str, Form()] = "",
                 note: Annotated[str, Form()] = ""):
    """Record that this one went out."""
    settings = load_settings()
    job = job_store.load(slug, settings.home)
    if job is None:
        return _back("/", error=f"There is no saved job called {slug!r}.")

    kinds = [k for k in sent if k in apply_models.SENT_KINDS]
    apply_store.record(job, on=on, channel=channel, sent=kinds, contact=contact,
                       note=note, home=settings.home)
    return _back(f"/jobs/{slug}", note="Recorded. Good luck.")


@router.post("/applications/{slug}/mark")
def move_application(slug: str, status: Annotated[str, Form()] = "",
                     on: Annotated[str, Form()] = "",
                     note: Annotated[str, Form()] = "",
                     back: Annotated[str, Form()] = ""):
    settings = load_settings()
    target = _own_path(back)
    before = apply_store.load(slug, settings.home)
    if before is None:
        return _back(target, error="No application recorded for that job.")
    if apply_store.mark(slug, status, on=on, note=note, home=settings.home) is None:
        allowed = ", ".join(before.next_states) or "nothing - it is closed"
        return _back(target, error=f"{before.label} is {before.status}; from there "
                                   f"you can go to {allowed}.")
    return _back(target, note=f"{before.label} is now {status}.")


@router.post("/applications/{slug}/note")
def note_application(slug: str, text: Annotated[str, Form()] = "",
                     back: Annotated[str, Form()] = ""):
    settings = load_settings()
    target = _own_path(back)
    if apply_store.add_note(slug, text, settings.home) is None:
        return _back(target, error="Nothing to note - no application, or an empty note.")
    return _back(target, note="Noted.")


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
