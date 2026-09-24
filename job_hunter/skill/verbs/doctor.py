"""Check the repo can do its job, before anything is built on it."""

from __future__ import annotations

from ... import paths
from ...profile import store as profile_store
from ...profile.models import Severity
from .. import exits


def add_arguments(parser) -> None:
    pass


def _browser() -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "Playwright is not installed. Run: pip install -e ."
    try:
        with sync_playwright() as playwright:
            playwright.chromium.launch(headless=True).close()
    except Exception:
        return "Chromium cannot start. Run: playwright install chromium"
    return ""


def run(args) -> int:
    from ..__main__ import emit

    # cv/README.md is the folder's own instructions, not somebody's CV.
    cvs = sorted(p.name for p in paths.cv_dir().glob("*")
                 if p.suffix.lower() in {".pdf", ".docx", ".txt", ".md", ".yaml", ".yml"}
                 and p.name.lower() != "readme.md")
    path = profile_store.profile_path()
    profile = profile_store.load(path)
    blocking = [i.message for i in profile.report() if i.severity == Severity.BLOCKING]
    browser = _browser()

    emit({
        "root": str(paths.root()),
        "cv_files": cvs,
        "profile": str(path),
        "profile_exists": path.exists(),
        "profile_ready": not blocking and path.exists(),
        "profile_problems": blocking,
        "browser_ready": not browser,
        "browser_problem": browser,
    })

    # There is no model to check. That is the point: Claude Code is the model.
    if not path.exists():
        if not cvs:
            print(f"No CV and no profile yet. Put your CV in {paths.cv_dir()}/ "
                  "- pdf, docx, txt, md or yaml.")
            return exits.BLOCKED
        print(f"No profile yet, but {', '.join(cvs)} is there to read.")
        return exits.OK
    if blocking:
        print("The profile is not usable yet:\n  " + "\n  ".join(blocking))
        return exits.BLOCKED
    if browser:
        print(browser)
        return exits.BLOCKED
    return exits.OK
