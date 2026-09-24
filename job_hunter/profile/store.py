"""Reading and writing the profile as human-editable YAML.

It sits at the repo root, beside the CV it was read from - see `paths`. It is
gitignored and a pre-commit hook refuses to let it be committed, because it is
somebody's career and their contact details.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .. import paths
from .models import Profile

PROFILE_NAME = paths.PROFILE_NAME


def profile_path(directory: Path | None = None) -> Path:
    """The profile's path. A directory argument still wins, which is what the
    tests use to keep a real profile out of the way."""
    return (directory / PROFILE_NAME) if directory else paths.profile_path()


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
