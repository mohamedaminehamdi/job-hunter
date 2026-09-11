"""Pages: read state, render it. No page changes anything."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from ... import render
from ...config import load_settings
from ...discover import criteria as criteria_mod
from ...discover import store as queue_store
from ...generate import store as doc_store
from ...jobs import store as job_store
from ...profile import store as profile_store
from ...profile.models import Severity
from ..templating import templates

router = APIRouter()


def _profile():
    settings = load_settings()
    return settings, profile_store.load(profile_store.profile_path(settings.home))


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, error: str = "", note: str = ""):
    settings, profile = _profile()
    jobs = job_store.all_jobs(settings.home)
    return templates.TemplateResponse(request, "index.html", {
        "profile": profile,
        "issues": profile.report(),
        "jobs": jobs,
        "queue_counts": queue_store.counts(settings.home),
        "settings": settings,
        "model_problem": settings.missing(),
        "error": error,
        "note": note,
    })


@router.get("/queue", response_class=HTMLResponse)
def queue_page(request: Request, show: str = "new", error: str = "", note: str = ""):
    """What the searches found, and the criteria that found it.

    The criteria editor lives on this page rather than its own: a queue full of
    the wrong jobs is fixed by editing the search, and the two should not be a
    navigation apart.
    """
    settings, profile = _profile()
    candidates = queue_store.load(settings.home)
    shown = ([c for c in candidates if c.status == show]
             if show in queue_store.STATUSES else candidates)
    path = criteria_mod.criteria_path(settings.home)
    criteria = criteria_mod.load(settings.home)
    return templates.TemplateResponse(request, "queue.html", {
        "candidates": shown,
        "show": show,
        "counts": queue_store.counts(settings.home),
        "criteria": criteria,
        "issues": criteria.report(),
        "path": path,
        "yaml_text": (path.read_text(encoding="utf-8") if path.exists()
                      else criteria_mod.example()),
        "sources": criteria.sources_enabled,
        "profile_ready": bool(profile.personal.full_name or profile.experience),
        "model_problem": settings.missing(),
        "error": error,
        "note": note,
    })


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, error: str = "", note: str = ""):
    settings, profile = _profile()
    path = profile_store.profile_path(settings.home)
    return templates.TemplateResponse(request, "profile.html", {
        "profile": profile,
        "issues": profile.report(),
        "path": path,
        "yaml_text": path.read_text(encoding="utf-8") if path.exists() else "",
        "error": error,
        "note": note,
    })


@router.get("/jobs/{slug}", response_class=HTMLResponse)
def job_page(request: Request, slug: str, error: str = "", note: str = ""):
    settings, profile = _profile()
    job = job_store.load(slug, settings.home)
    if job is None:
        return templates.TemplateResponse(request, "error.html", {
            "title": "No such job",
            "message": f"There is no saved job called {slug!r}.",
        }, status_code=404)

    return templates.TemplateResponse(request, "job.html", {
        "job": job,
        "profile": profile,
        "cv": doc_store.load(slug, "cv", settings.home),
        "letter": doc_store.load(slug, "letter", settings.home),
        "answers": doc_store.load_answers(slug, settings.home),
        "themes": sorted(render.THEMES),
        "error": error,
        "note": note,
    })


@router.get("/jobs/{slug}/source", response_class=PlainTextResponse)
def job_source(slug: str):
    """What the model actually read. The review step's receipt."""
    settings = load_settings()
    job = job_store.load(slug, settings.home)
    if job is None:
        return PlainTextResponse("No such job.", status_code=404)
    return PlainTextResponse(job.source_text or "(this job was entered by hand)")


@router.get("/jobs/{slug}/{kind}", response_class=HTMLResponse)
def review_page(request: Request, slug: str, kind: str, error: str = "", note: str = ""):
    """The review step: the document, its issues, and the profile behind it."""
    settings, profile = _profile()
    job = job_store.load(slug, settings.home)
    document = doc_store.load(slug, kind, settings.home) if kind in doc_store.KINDS else None
    if job is None or document is None:
        return templates.TemplateResponse(request, "error.html", {
            "title": "Nothing to review",
            "message": "That document has not been generated yet.",
        }, status_code=404)

    issues = document.all_issues
    return templates.TemplateResponse(request, "review.html", {
        "job": job,
        "kind": kind,
        "document": document,
        "profile": profile,
        "issues": issues,
        "blocking": [i for i in issues if i.severity is Severity.BLOCKING],
        "themes": sorted(render.THEMES),
        "pdf_name": f"{slug}-{kind}.pdf",
        "pdf_exists": (settings.output_dir / f"{slug}-{kind}.pdf").exists(),
        "error": error,
        "note": note,
    })


@router.get("/jobs/{slug}/{kind}/preview", response_class=HTMLResponse)
def preview(slug: str, kind: str, theme: str = "neutral", branded: str = ""):
    """The document exactly as it will print. Shown in the review page's frame."""
    settings = load_settings()
    document = doc_store.load(slug, kind, settings.home) if kind in doc_store.KINDS else None
    if document is None:
        return HTMLResponse("<p>Nothing generated yet.</p>", status_code=404)

    chosen = render.resolve(theme)
    if branded:
        job = job_store.load(slug, settings.home)
        chosen = render.branded(job.brand_color if job else "", base=chosen)
    return HTMLResponse(render.to_html(document, theme=chosen))


