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

from . import __version__, discover, render
from .apply import models as apply_models
from .apply import store as apply_store
from .config import Settings, load_settings
from .discover import criteria as criteria_mod
from .discover import store as queue_store
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
    LLMError, render.ExportBlocked, render.PdfError, apply_models.ApplyError,
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
        "applications_open": apply_store.counts(settings.home)["open"],
        "applications_quiet": apply_store.counts(settings.home)["quiet"],
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
    _out(f"sent      {payload['applications_open']} open, "
         f"{payload['applications_quiet']} with no reply")
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
    return _finish(drafted, None, exportable=False)


def cmd_search(args: argparse.Namespace, settings: Settings) -> int:
    """Search every configured source and queue what scores well enough."""
    criteria = criteria_mod.load(settings.home)
    if not criteria.is_searchable:
        _out(f"Nothing to search yet. Edit {criteria_mod.criteria_path(settings.home)}:")
        _issues(criteria.report())
        _out("\nA starting point:\n")
        _out(criteria_mod.example())
        return 1

    report = discover.search(_require_profile(settings), criteria, settings.home,
                             timeout=args.timeout, only=tuple(args.source or ()))
    payload = {**report.model_dump(mode="json"), "summary": report.summary()}
    if _emit(payload, args.json):
        return 0

    _out(report.summary())
    for outcome in report.outcomes:
        mark = "!" if outcome.error else " "
        detail = outcome.error or f"{outcome.found} listing(s)"
        _out(f"{mark} {outcome.label:<28} {detail}")
    if report.added:
        _out(f"\n{report.added} new to look at: job-hunter queue")
    return 0


#: A decided candidate is only ever shown alongside undecided ones, so the mark
#: is the whole difference between them on the line.
_MARKS = {queue_store.NEW: " ", queue_store.PICKED: "+", queue_store.DISMISSED: "-"}


def _queue_line(candidate) -> str:
    listing = candidate.listing
    where = listing.location or listing.workplace or "-"
    return (f"{_MARKS.get(candidate.status, '?')} {candidate.match.score:>3}  "
            f"{candidate.id:<46} {listing.label[:50]:<52} {where[:22]}")


def cmd_queue(args: argparse.Namespace, settings: Settings) -> int:
    """Show what the searches turned up and what you decided about it."""
    candidates = queue_store.load(settings.home)
    if args.status:
        candidates = [c for c in candidates if c.status == args.status]
    elif not args.all:
        candidates = [c for c in candidates if c.status == queue_store.NEW]

    if _emit({"counts": queue_store.counts(settings.home),
              "candidates": [c.model_dump(mode="json") for c in candidates]}, args.json):
        return 0

    if not candidates:
        _out("Nothing waiting. Run 'job-hunter search' to fill the queue.")
        return 0
    for candidate in candidates:
        _out(_queue_line(candidate))
        if args.why:
            for reason in candidate.match.reasons:
                _out(f"       - {reason}")
    counts = queue_store.counts(settings.home)
    _out(f"\n{counts['new']} waiting, {counts['picked']} picked, "
         f"{counts['dismissed']} dismissed.")
    _out("Pick one: job-hunter pick <id>")
    return 0


def _require_candidate(candidate_id: str, settings: Settings):
    candidate = queue_store.get(candidate_id, settings.home)
    if candidate is None:
        raise GenerationError(
            f"No queued job with id {candidate_id!r}. Run 'job-hunter queue' to see them."
        )
    return candidate


def cmd_pick(args: argparse.Namespace, settings: Settings) -> int:
    """Promote a queued listing to a saved job: fetch the posting and parse it.

    This is the only point in discovery that costs a page load and a model call,
    which is why it happens per job you chose rather than per search hit.
    """
    candidate = _require_candidate(args.id, settings)
    job = job_parse.from_url(candidate.listing.url, timeout=args.timeout, settings=settings)
    saved = job_store.save(job, settings.home)
    queue_store.set_status(candidate.id, queue_store.PICKED, settings.home,
                           job_slug=job.slug)

    payload = {"id": candidate.id, "slug": job.slug, "saved_to": str(saved),
               "usable": job.is_usable, "problem": job.missing()}
    if _emit(payload, args.json):
        return 0

    _out(f"{job.label}  [{job.slug}]")
    _out(f"saved to {saved}")
    if (problem := job.missing()) is not None:
        _out(f"\n! {problem}")
    _out(f"\nTailor to it: job-hunter cv {job.slug}")
    return 0


def cmd_dismiss(args: argparse.Namespace, settings: Settings) -> int:
    """Drop a listing, for good. Later searches will not re-queue it."""
    candidate = _require_candidate(args.id, settings)
    queue_store.set_status(candidate.id, queue_store.DISMISSED, settings.home)
    if _emit({"id": candidate.id, "status": queue_store.DISMISSED}, args.json):
        return 0
    _out(f"Dismissed {candidate.listing.label}.")
    return 0


# --- what you actually sent -------------------------------------------------

#: One mark per state, in the spirit of the queue's. A blank for the common
#: case, so the exceptions are what catches the eye.
_APPLY_MARKS = {
    apply_models.APPLIED: " ", apply_models.INTERVIEWING: ">",
    apply_models.OFFER: "*", apply_models.REJECTED: "x",
    apply_models.WITHDRAWN: "-",
}


def _application_line(application) -> str:
    quiet = application.days_quiet
    age = f"{quiet}d" if quiet is not None else "-"
    return (f"{_APPLY_MARKS.get(application.status, '?')} "
            f"{application.applied_on or '?':<10}  {application.job_slug:<38} "
            f"{application.label[:44]:<46} {application.status:<13} {age:>5}")


def cmd_applied(args: argparse.Namespace, settings: Settings) -> int:
    """Record that you sent an application."""
    job = _require(args.slug, settings)
    application = apply_store.record(
        job, on=args.on or "", channel=args.channel or "", sent=args.sent,
        contact=args.contact or "", note=args.note or "", home=settings.home)
    saved = apply_store.application_path(job.slug, settings.home)

    payload = {"slug": job.slug, "saved_to": str(saved),
               "application": application.model_dump(mode="json")}
    if _emit(payload, args.json):
        return 0

    _out(f"Applied to {application.label}  [{job.slug}]")
    details = [application.applied_on, application.channel]
    if application.sent:
        details.append(f"sent {', '.join(application.sent)}")
    _out(" · ".join(d for d in details if d))
    _out(f"saved to {saved}")

    # The documents on disk are a guess at what you attached, never a record of
    # it, so this hints and does not fill anything in.
    if not application.sent:
        have = [kind for kind in apply_models.SENT_KINDS
                if doc_store.load(job.slug, kind, settings.home) is not None]
        if have:
            flags = " ".join(f"--with {kind}" for kind in have)
            _out(f"\n! You have a tailored {' and a '.join(have)} for this job. "
                 f"If you sent them:\n  job-hunter applied {job.slug} {flags}")
    _out(f"\nNothing back in {apply_models.FOLLOW_UP_DAYS} days? "
         f"job-hunter note {job.slug} \"chased them\"")
    return 0


def cmd_mark(args: argparse.Namespace, settings: Settings) -> int:
    """Move an application on: they replied, or they did not."""
    before = apply_store.load(args.slug, settings.home)
    if before is None:
        raise apply_models.ApplyError(
            f"No application recorded for {args.slug!r}. "
            f"Record one first: job-hunter applied {args.slug}"
        )
    moved = apply_store.mark(args.slug, args.state, on=args.on or "",
                             note=args.note or "", home=settings.home)
    if moved is None:
        allowed = ", ".join(before.next_states) or "nothing - it is closed"
        raise apply_models.ApplyError(
            f"{before.label} is {before.status}; from there you can go to "
            f"{allowed}. Edit {apply_store.application_path(args.slug, settings.home)} "
            "if you need to re-open it."
        )

    if _emit({"slug": args.slug, "application": moved.model_dump(mode="json")}, args.json):
        return 0
    out = 0 if (days := before.days_quiet) is None else days
    _out(f"{moved.label}: {before.status} -> {moved.status}  ({out} days out)")
    if args.note:
        _out(args.note)
    return 0


def cmd_note(args: argparse.Namespace, settings: Settings) -> int:
    """Add a dated note, which also stops it showing as gone quiet."""
    text = sys.stdin.read() if args.text == "-" else args.text
    noted = apply_store.add_note(args.slug, text, settings.home)
    if noted is None:
        raise apply_models.ApplyError(
            f"Nothing to note against {args.slug!r} - no application recorded, "
            "or the note was empty."
        )
    if _emit({"slug": args.slug, "application": noted.model_dump(mode="json")}, args.json):
        return 0
    _out(f"{noted.label}: {noted.history[-1].note}")
    return 0


def _nothing_to_show(args: argparse.Namespace, counts: dict, quiet_for: int) -> str:
    """Why the list is empty, which is rarely "you have sent nothing".

    An empty list under a filter used to read as an empty record, which told
    someone with a healthy job hunt that they had not started one.
    """
    if not counts["total"]:
        return "Nothing recorded yet. After you send one: job-hunter applied <slug>"
    if args.stale is not None:
        return (f"Nothing has gone quiet - everything still open has had something "
                f"happen in the last {quiet_for} days.")
    if args.status:
        return f"No application is marked {args.status!r}. See them all with --all."
    return (f"Nothing open. {counts['total']} closed - "
            "see them with: job-hunter applications --all")


def cmd_applications(args: argparse.Namespace, settings: Settings) -> int:
    """What you have sent, and what is still outstanding."""
    quiet_for = args.stale if args.stale is not None else apply_models.FOLLOW_UP_DAYS
    if args.stale is not None:
        shown = apply_store.outstanding(settings.home, quiet_for=quiet_for)
    else:
        shown = apply_store.all_applications(settings.home)
        if args.status:
            shown = [a for a in shown if a.status == args.status]
        elif not args.all:
            shown = [a for a in shown if a.is_open]

    counts = apply_store.counts(settings.home)
    if _emit({"counts": counts,
              "applications": [a.model_dump(mode="json") for a in shown]}, args.json):
        return 0

    if not shown:
        _out(_nothing_to_show(args, counts, quiet_for))
        return 0
    for application in shown:
        _out(_application_line(application))

    _out(f"\n{counts['open']} out ({counts[apply_models.APPLIED]} applied, "
         f"{counts[apply_models.INTERVIEWING]} interviewing), "
         f"{counts[apply_models.OFFER]} offer(s), "
         f"{counts['total'] - counts['open']} closed.")
    if args.stale is None and counts["quiet"]:
        _out(f"{counts['quiet']} heard nothing for {quiet_for}+ days: "
             "job-hunter applications --stale")
    return 0


def _maybe_export(args: argparse.Namespace, document, job, stem: str,
                  settings: Settings) -> Path | None:
    """Write the PDF if asked. `--export` on a blocked document is an error."""
    if not getattr(args, "export", False):
        return None
    theme = render.resolve(getattr(args, "theme", None))
    if getattr(args, "branded", False):
        theme = render.branded(job.brand_color, base=theme)
    return render.export(document, settings.output_dir / f"{stem}.pdf", theme=theme)


def _finish(document, exported: Path | None, *, exportable: bool = True) -> int:
    """Print the issues, then say what can be done next.

    `exportable` is False for a document with no PDF to write - an application
    answer is pasted into a form - so the hint does not name a flag that command
    does not have.
    """
    issues = document.all_issues
    if issues:
        _out(f"\n{len(issues)} thing(s) to check before you send this:")
        _issues(issues)
    if exported:
        _out(f"\nPDF: {exported}")
    elif getattr(document, "blocking", None):
        _out("\nThis will not export until the blocking items above are fixed.")
    elif exportable:
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
    parser.add_argument("--version", action="version", version=f"job-hunter {__version__}")
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

    search = subparsers.add_parser("search", help="search your sources and fill the queue")
    search.add_argument("--source", action="append", choices=sorted(discover.sources.ALL),
                        help="only this source (repeatable)")
    search.add_argument("--timeout", type=int, default=30,
                        help="per-source timeout, seconds")

    queue = subparsers.add_parser("queue", help="show what the searches found")
    queue.add_argument("--all", action="store_true", help="including decided ones")
    queue.add_argument("--status", choices=queue_store.STATUSES, help="only this state")
    queue.add_argument("--why", action="store_true", help="show the scoring reasons")

    pick = subparsers.add_parser("pick", help="turn a queued listing into a saved job")
    pick.add_argument("id", help="an id from 'job-hunter queue'")
    pick.add_argument("--timeout", type=int, default=30)

    dismissed = subparsers.add_parser("dismiss", help="drop a queued listing for good")
    dismissed.add_argument("id", help="an id from 'job-hunter queue'")

    # `applied`, not `apply`: this records a fact, it does not submit anything,
    # and `apply` belongs to the assisted-application work that would.
    applied = subparsers.add_parser("applied", help="record that you sent an application")
    applied.add_argument("slug", help="a job slug from 'job-hunter jobs'")
    applied.add_argument("--on", help="the date you sent it (default: today)")
    applied.add_argument("--channel", help="how it went out, e.g. 'company form'")
    applied.add_argument("--with", dest="sent", action="append",
                         choices=sorted(apply_models.SENT_KINDS),
                         help="a document you sent (repeatable)")
    applied.add_argument("--contact", help="who you are dealing with")
    applied.add_argument("--note", help="anything worth remembering")

    marked = subparsers.add_parser("mark", help="move an application on")
    marked.add_argument("slug")
    marked.add_argument("state", choices=sorted(apply_models.STATES))
    marked.add_argument("--on", help="when it happened (default: now)")
    marked.add_argument("--note")

    noted = subparsers.add_parser("note", help="add a dated note to an application")
    noted.add_argument("slug")
    noted.add_argument("text", help="the note, or - to read it from stdin")

    applications = subparsers.add_parser("applications",
                                         help="what you have sent, and what is outstanding")
    applications.add_argument("--all", action="store_true", help="including closed ones")
    applications.add_argument("--status", choices=sorted(apply_models.STATES))
    applications.add_argument("--stale", nargs="?", type=int,
                              const=apply_models.FOLLOW_UP_DAYS, default=None,
                              metavar="DAYS", help="only the ones gone quiet")

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
    "search": cmd_search, "queue": cmd_queue, "pick": cmd_pick, "dismiss": cmd_dismiss,
    "applied": cmd_applied, "mark": cmd_mark, "note": cmd_note,
    "applications": cmd_applications,
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
