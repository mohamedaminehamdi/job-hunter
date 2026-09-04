"""Reading and writing the profile as human-editable YAML.

Kept outside the repo (``~/.job-hunter/`` by default) so nobody commits their
CV or an API key by accident.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from .models import Profile

DEFAULT_DIR = Path(os.environ.get("JOB_HUNTER_HOME", Path.home() / ".job-hunter"))
PROFILE_NAME = "profile.yaml"


def profile_path(directory: Path | None = None) -> Path:
    return (directory or DEFAULT_DIR) / PROFILE_NAME


def load(path: Path | None = None) -> Profile:
    """Load a profile, or an empty one if there is nothing saved yet.

    Malformed YAML yields an empty profile rather than raising: the web UI must
    always have something to render, and `Profile.report()` is where the user
    finds out what is wrong.
    """
    target = path or profile_path()
    if not target.exists():
        return Profile()
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return Profile()
    if not isinstance(raw, dict):
        return Profile()
    return from_dict(raw)


def from_dict(raw: dict) -> Profile:
    """Build a Profile from loose data, dropping unknown keys.

    Tolerates hand-edited YAML and LLM-extracted output, both of which contain
    surprises. Unparseable sections become empty rather than fatal.
    """
    known = {k: v for k, v in raw.items() if k in Profile.model_fields}
    try:
        return Profile.model_validate(known)
    except Exception:
        # Salvage what parses: try each top-level section on its own.
        profile = Profile()
        for key, value in known.items():
            try:
                profile = profile.model_copy(
                    update={key: Profile.model_validate({key: value}).__getattribute__(key)}
                )
            except Exception:
                continue
        return profile


def save(profile: Profile, path: Path | None = None) -> Path:
    """Write the profile as YAML, creating the directory if needed."""
    target = path or profile_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    data = profile.model_dump(mode="json", exclude_defaults=False)
    target.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    return target
