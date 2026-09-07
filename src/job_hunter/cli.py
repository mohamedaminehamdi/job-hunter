"""The command line: everything the tool does, without the browser.

Deliberately the same code path as the web layer - both are thin shells over
`profile`, `jobs`, `generate` and `render`. If a thing can be done in one and
not the other, that is a bug rather than a design.

Nothing here prints a stack trace at the user: every failure the library raises
on purpose carries a message meant to be read, and `main` turns those into one
line on stderr and exit 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import render
from .config import Settings, load_settings
from .generate import answers as answers_mod
from .generate import cover_letter as letter_mod
from .generate import cv as cv_mod
from .generate import store as doc_store
from .generate.errors import GenerationError
from .generate.llm import LLMError
from .jobs import parse as job_parse
from .jobs import store as job_store
from .jobs.fetch import FetchError
from .profile import intake
from .profile import store as profile_store
from .profile.models import Profile, Severity

#: Everything the library raises on purpose. All of these carry a user-facing message.
USER_ERRORS = (
    intake.IntakeError, FetchError, job_parse.ParseError, GenerationError,
    LLMError, render.ExportBlocked, render.PdfError,
)


# --- output helpers -------------------------------------------------------

def _out(text: str = "") -> None:
    print(text)


def _issues(items: list, *, indent: str = "  ") -> None:
    """Print an issue checklist, worst first, with a mark per severity."""
    marks = {Severity.BLOCKING: "x", Severity.WARNING: "!", Severity.INFO: "-"}
    for issue in items:
        _out(f"{indent}[{marks[issue.severity]}] {issue.path}: {issue.message}")


def _emit(payload: dict[str, Any], as_json: bool) -> bool:
    """Print `payload` as JSON and report whether that is all the output needed."""
    if as_json:
        _out(json.dumps(payload, indent=2, default=str))
    return as_json


# --- commands -------------------------------------------------------------

def cmd_doctor(args: argparse.Namespace, settings: Settings) -> int:
    """Report whether the tool can actually do its job right now."""
    profile = profile_store.load(profile_store.profile_path(settings.home))
    blocking = [i for i in profile.report() if i.severity is Severity.BLOCKING]
    browser = _browser_status()
    payload = {
        "model": settings.model,
        "model_ready": settings.missing() is None,
        "model_problem": settings.missing(),
        "browser_ready": browser is None,
        "browser_problem": browser,
        "home": str(settings.home),
        "profile": str(profile_store.profile_path(settings.home)),
        "profile_exists": profile_store.profile_path(settings.home).exists(),
        "profile_ready": not blocking,
        "jobs_saved": len(job_store.all_jobs(settings.home)),
    }
    if _emit(payload, args.json):
        return 0

    _out(f"model     {settings.model}")
    _out(f"          {settings.missing() or 'ready'}")
    _out(f"browser   {browser or 'ready'}")
    _out(f"home      {settings.home}")
    _out(f"profile   {'ready' if not blocking else 'incomplete'} "
         f"({profile_store.profile_path(settings.home)})")
    _issues(blocking)
    _out(f"jobs      {payload['jobs_saved']} saved")
    return 0


def _browser_status() -> str | None:
    """None if Chromium can start, else what to do about it."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "Playwright is not installed: pip install playwright"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
    except Exception:
        return "Chromium cannot start. Run: playwright install chromium"
    return None


def cmd_import(args: argparse.Namespace, settings: Settings) -> int:
    """Import a CV into the profile."""
    path = Path(args.file)
    result = intake.from_file(path, settings=settings) if path.suffix.lower() not in {
        ".yaml", ".yml"} else intake.from_file(path)
    saved = profile_store.save(result.profile, profile_store.profile_path(settings.home))

    payload = {
        "saved_to": str(saved),
        "extracted": result.extracted,
        "issues": [i.model_dump(mode="json") for i in result.profile.report()],
        "renderable": result.profile.is_renderable,
    }
    if _emit(payload, args.json):
        return 0

    _out(f"Imported {path.name} -> {saved}")
    if result.extracted:
        _out("A model read this CV, so check the YAML before you send anything from it.")
    return _report_profile(result.profile)


def cmd_profile(args: argparse.Namespace, settings: Settings) -> int:
    """Show the saved profile's state."""
    target = profile_store.profile_path(settings.home)
    profile = profile_store.load(target)
    payload = {
        "path": str(target),
        "exists": target.exists(),
        "name": profile.personal.full_name,
        "roles": len(profile.experience),
        "renderable": profile.is_renderable,
        "issues": [i.model_dump(mode="json") for i in profile.report()],
    }
    if _emit(payload, args.json):
        return 0

    if not target.exists():
        _out(f"No profile yet at {target}. Import a CV: job-hunter import cv.pdf")
        return 1
    _out(f"{profile.personal.full_name or '(no name)'} - {len(profile.experience)} "
         f"role(s), {len(profile.education)} degree(s)  [{target}]")
    return _report_profile(profile)


def _report_profile(profile: Profile) -> int:
    issues = profile.report()
    if not issues:
        _out("No problems found.")
        return 0
    _out(f"{len(issues)} thing(s) to look at:")
    _issues(issues)
    return 0 if profile.is_renderable else 1


def cmd_job(args: argparse.Namespace, settings: Settings) -> int:
    """Fetch or read a job posting, and save it."""
    if args.text or args.source == "-":
        text = sys.stdin.read() if args.source in ("-", None) else args.source
        job = job_parse.from_text(text, settings=settings)
    else:
        job = job_parse.from_url(args.source, timeout=args.timeout, settings=settings)

    saved = job_store.save(job, settings.home)
    payload = {"slug": job.slug, "saved_to": str(saved), "usable": job.is_usable,
               "problem": job.missing(), **job.model_dump(mode="json", exclude={"source_text"})}
    if _emit(payload, args.json):
        return 0

    _out(f"{job.label}  [{job.slug}]")
    _out(f"saved to {saved}")
    if (problem := job.missing()) is not None:
        _out(f"\n! {problem}")
    _out()
    _out(job.brief())
    return 0


def cmd_jobs(args: argparse.Namespace, settings: Settings) -> int:
    """List saved jobs."""
    jobs = job_store.all_jobs(settings.home)
    if _emit({"jobs": [{"slug": j.slug, "label": j.label, "fetched_at": j.fetched_at,
                        "usable": j.is_usable} for j in jobs]}, args.json):
        return 0
    if not jobs:
        _out("No jobs saved yet. Add one: job-hunter job <url>")
        return 0
    for job in jobs:
        mark = " " if job.is_usable else "!"
        _out(f"{mark} {job.slug:<40} {job.label}")
    return 0


def _require(slug: str, settings: Settings):
    job = job_store.load(slug, settings.home)
    if job is None:
        raise GenerationError(
            f"No saved job called {slug!r}. Run 'job-hunter jobs' to see what there is."
        )
    return job


def _require_profile(settings: Settings) -> Profile:
    profile = profile_store.load(profile_store.profile_path(settings.home))
    if not profile.personal.full_name and not profile.experience:
        raise GenerationError(
            "Your profile is empty. Import your CV first: job-hunter import cv.pdf"
        )
    return profile


def cmd_cv(args: argparse.Namespace, settings: Settings) -> int:
    """Tailor the CV to a saved job."""
    job = _require(args.slug, settings)
    document = cv_mod.tailor(_require_profile(settings), job, settings=settings)
    saved = doc_store.save(document, job.slug, "cv", settings.home)
    exported = _maybe_export(args, document, job, f"{job.slug}-cv", settings)

    payload = {"saved_to": str(saved), "exported_to": str(exported) if exported else None,
               "issues": [i.model_dump(mode="json") for i in document.all_issues],
               "document": document.model_dump(mode="json", exclude={"issues"})}
    if _emit(payload, args.json):
        return 0

    _out(f"Tailored CV for {job.label}")
    _out(f"saved to {saved}")
    _out(f"\nSummary: {document.summary}")
    for role in document.experience:
        _out(f"\n{role.position}, {role.company}  {role.period}")
        for bullet in role.bullets:
            _out(f"  - {bullet}")
    if document.skills:
        _out(f"\nSkills: {', '.join(document.skills)}")
    return _finish(document, exported)


def cmd_letter(args: argparse.Namespace, settings: Settings) -> int:
    """Write a cover letter for a saved job."""
    job = _require(args.slug, settings)
    letter = letter_mod.write(_require_profile(settings), job, settings=settings)
    saved = doc_store.save(letter, job.slug, "letter", settings.home)
    exported = _maybe_export(args, letter, job, f"{job.slug}-letter", settings)

    payload = {"saved_to": str(saved), "exported_to": str(exported) if exported else None,
               "issues": [i.model_dump(mode="json") for i in letter.all_issues],
               "letter": letter.model_dump(mode="json", exclude={"issues"})}
    if _emit(payload, args.json):
        return 0

    _out(letter.body)
    _out(f"\nsaved to {saved}")
    return _finish(letter, exported)


def cmd_answer(args: argparse.Namespace, settings: Settings) -> int:
    """Draft an answer to one application question."""
    job = _require(args.slug, settings)
    question = args.question if args.question != "-" else sys.stdin.read()
    drafted = answers_mod.answer(_require_profile(settings), job, question,
                                 words=args.words, settings=settings)
    saved = doc_store.add_answer(drafted, job.slug, settings.home)

    payload = {"saved_to": str(saved), **drafted.model_dump(mode="json", exclude={"issues"}),
               "issues": [i.model_dump(mode="json") for i in drafted.all_issues]}
    if _emit(payload, args.json):
        return 0

    _out(f"Q: {drafted.question}")
    _out(f"\n{drafted.text}\n")
    _out(f"({drafted.word_count} words, saved to {saved})")
    return _finish(drafted, None)


def _maybe_export(args: argparse.Namespace, document, job, stem: str,
                  settings: Settings) -> Path | None:
    """Write the PDF if asked. `--export` on a blocked document is an error."""
    if not getattr(args, "export", False):
        return None
    theme = render.resolve(getattr(args, "theme", None))
    if getattr(args, "branded", False):
        theme = render.branded(job.brand_color, base=theme)
    return render.export(document, settings.output_dir / f"{stem}.pdf", theme=theme)


def _finish(document, exported: Path | None) -> int:
    issues = document.all_issues
    if issues:
        _out(f"\n{len(issues)} thing(s) to check before you send this:")
        _issues(issues)
    if exported:
        _out(f"\nPDF: {exported}")
    elif getattr(document, "blocking", None):
        _out("\nThis will not export until the blocking items above are fixed.")
    else:
        _out("\nRe-run with --export to write the PDF.")
    return 0


def cmd_serve(args: argparse.Namespace, settings: Settings) -> int:
    """Run the web UI."""
    import uvicorn
    _out(f"Job Hunter on http://{args.host}:{args.port}  (profile: {settings.home})")
    uvicorn.run("job_hunter.web:app", host=args.host, port=args.port,
                reload=args.reload, log_level="warning")
    return 0


# --- wiring ---------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-hunter",
        description="Tailor your CV, cover letter and application answers to a job.",
    )
    parser.add_argument("--json", action="store_true",
                        help="machine-readable output instead of prose")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="check the model, the browser and the profile")

    imported = subparsers.add_parser("import", help="import a CV (pdf/docx/txt/md/yaml)")
    imported.add_argument("file")

    subparsers.add_parser("profile", help="show the saved profile and its problems")

    job = subparsers.add_parser("job", help="fetch a job posting and save it")
    job.add_argument("source", nargs="?", default="-",
                     help="a URL, or - to read the description from stdin")
    job.add_argument("--text", action="store_true",
                     help="treat the argument as description text, not a URL")
    job.add_argument("--timeout", type=int, default=30, help="page load timeout, seconds")

    subparsers.add_parser("jobs", help="list saved jobs")

    for name, help_text in (("cv", "tailor your CV to a saved job"),
                            ("letter", "write a cover letter for a saved job")):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("slug", help="a job slug from 'job-hunter jobs'")
        command.add_argument("--export", action="store_true", help="also write the PDF")
        command.add_argument("--theme", default="neutral", choices=sorted(render.THEMES),
                             help="document styling")
        if name == "letter":
            command.add_argument("--branded", action="store_true",
                                 help="use the company's colour, if the page had one")

    answer = subparsers.add_parser("answer", help="draft an application answer")
    answer.add_argument("slug")
    answer.add_argument("question", help="the question, or - to read it from stdin")
    answer.add_argument("--words", type=int, default=answers_mod.DEFAULT_WORDS)

    serve = subparsers.add_parser("serve", help="run the web UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--reload", action="store_true", help=argparse.SUPPRESS)

    return parser


COMMANDS = {
    "doctor": cmd_doctor, "import": cmd_import, "profile": cmd_profile,
    "job": cmd_job, "jobs": cmd_jobs, "cv": cmd_cv, "letter": cmd_letter,
    "answer": cmd_answer, "serve": cmd_serve,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    try:
        return COMMANDS[args.command](args, settings)
    except USER_ERRORS as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
