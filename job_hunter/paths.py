"""Where everything lives.

The premise is "clone the repo, drop your CV in it, everything is here", so
everything is here: the CV in `cv/`, the profile beside it, and one directory
per job under `runs/`. A friend debugging their profile should find it next to
their CV, not in a dotfile directory they did not know existed.

All three are gitignored, and a pre-commit hook refuses a commit that touches
them - `.gitignore` is advisory, and across ten forks one `git add -f` is
inevitable.
"""

from __future__ import annotations

import os
from pathlib import Path


def _find_root() -> Path:
    """The repo root, found by looking for pyproject.toml rather than counting
    directories.

    Counting broke the moment the package moved up a level: `parents[2]` went
    from the repo to the folder above it, and every test overrides this with
    JOB_HUNTER_HOME so nothing noticed. A marker cannot drift that way.
    """
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return here.parents[1]


#: `JOB_HUNTER_HOME` overrides it, which is what the tests use.
ROOT = Path(os.environ.get("JOB_HUNTER_HOME") or _find_root())

CV_DIR = "cv"
RUNS_DIR = "runs"
PROFILE_NAME = "profile.yaml"
LOG_NAME = "log.md"


def root() -> Path:
    """Re-read each call so a test can point the whole tool somewhere else."""
    return Path(os.environ.get("JOB_HUNTER_HOME") or _find_root())


def cv_dir(base: Path | None = None) -> Path:
    return (base or root()) / CV_DIR


def runs_dir(base: Path | None = None) -> Path:
    return (base or root()) / RUNS_DIR


def profile_path(base: Path | None = None) -> Path:
    return (base or root()) / PROFILE_NAME


def log_path(base: Path | None = None) -> Path:
    return runs_dir(base) / LOG_NAME
