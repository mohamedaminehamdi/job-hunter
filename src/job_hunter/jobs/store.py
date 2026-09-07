"""Saving job postings as YAML, one file per job.

Under ``~/.job-hunter/jobs/<slug>.yaml``, so a posting survives the browser tab
it came from and can be re-tailored later without re-fetching. Plain YAML for
the same reason the profile is: the user can read and fix it.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ..config import load_settings
from .models import Job, from_dict

DIRNAME = "jobs"


def jobs_dir(home: Path | None = None) -> Path:
    return (home or load_settings().home) / DIRNAME


def job_path(slug: str, home: Path | None = None) -> Path:
    return jobs_dir(home) / f"{slug}.yaml"


def save(job: Job, home: Path | None = None) -> Path:
    """Write a job, keyed by its slug. Re-fetching the same job overwrites it."""
    target = job_path(job.slug, home)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(job.model_dump(mode="json"), sort_keys=False,
                       allow_unicode=True, width=100),
        encoding="utf-8",
    )
    return target


def load(slug: str, home: Path | None = None) -> Job | None:
    """One job by slug, or None. Malformed YAML reads as missing, never raises."""
    target = job_path(slug, home)
    if not target.exists():
        return None
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    return from_dict(raw) if isinstance(raw, dict) else None


def all_jobs(home: Path | None = None) -> list[Job]:
    """Every saved job, most recently fetched first."""
    directory = jobs_dir(home)
    if not directory.is_dir():
        return []
    jobs = [job for path in sorted(directory.glob("*.yaml"))
            if (job := load(path.stem, home)) is not None]
    return sorted(jobs, key=lambda job: job.fetched_at, reverse=True)


def delete(slug: str, home: Path | None = None) -> bool:
    target = job_path(slug, home)
    if not target.exists():
        return False
    target.unlink()
    return True
