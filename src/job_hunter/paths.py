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

#: The repo root: three levels up from this file (src/job_hunter/paths.py).
#: `JOB_HUNTER_HOME` overrides it, which is what the tests use.
ROOT = Path(os.environ.get("JOB_HUNTER_HOME") or Path(__file__).resolve().parents[2])

CV_DIR = "cv"
RUNS_DIR = "runs"
PROFILE_NAME = "profile.yaml"
LOG_NAME = "log.md"


def root() -> Path:
    """Re-read each call so a test can point the whole tool somewhere else."""
    return Path(os.environ.get("JOB_HUNTER_HOME") or ROOT)


def cv_dir(base: Path | None = None) -> Path:
    return (base or root()) / CV_DIR


def runs_dir(base: Path | None = None) -> Path:
    return (base or root()) / RUNS_DIR


def profile_path(base: Path | None = None) -> Path:
    return (base or root()) / PROFILE_NAME


def log_path(base: Path | None = None) -> Path:
    return runs_dir(base) / LOG_NAME
