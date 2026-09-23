"""One directory per job, holding everything produced for it.

`runs/<date>-<slug>/`. The date prefix means re-running the same job on the same
day overwrites, which is what you want while iterating, and two different jobs
at the same company a month apart do not collide.

The slug is not known until the posting has been read, so fetching writes to
`runs/.incoming/<hash>/` and the parse step renames it. Every command prints the
directory it settled on, so the skill learns the path from the tool instead of
guessing it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .. import paths

INCOMING = ".incoming"


def incoming(url: str, base: Path | None = None) -> Path:
    """Where a fetch lands before anyone knows what the job is called."""
    digest = hashlib.sha1(url.encode()).hexdigest()[:10]
    return paths.runs_dir(base) / INCOMING / digest


def settled(slug: str, base: Path | None = None, *, on: str = "") -> Path:
    day = on or datetime.now(UTC).date().isoformat()
    return paths.runs_dir(base) / f"{day}-{slug}"


def promote(source: Path, slug: str, base: Path | None = None) -> Path:
    """Move a fetched run to its real name, now that the job has been read."""
    target = settled(slug, base)
    if target.resolve() == source.resolve():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(source), str(target))
    return target


def resolve(given: str, base: Path | None = None) -> Path:
    """The run directory a caller named, as an absolute path inside `runs/`.

    A run is addressed by name, never by an arbitrary path: everything this
    tool writes belongs under `runs/`, and a directory argument that can escape
    it is a directory argument that will.
    """
    candidate = Path(given)
    if not candidate.is_absolute():
        candidate = paths.runs_dir(base) / candidate.name \
            if candidate.parent.name in ("", ".", paths.RUNS_DIR) else candidate
    candidate = candidate.resolve()
    runs = paths.runs_dir(base).resolve()
    if runs not in candidate.parents:
        raise ValueError(f"{given} is not a run directory under {runs}")
    return candidate


#: What each file is for, so a missing one can say what to do about it.
_NEEDED = {
    "job.yaml": "that run has no parsed posting yet - run `skill job --run <run>` first",
    "page.txt": "that run has no posting text - run `skill fetch <url>` first",
    "cv.yaml": "that run has no tailored CV yet - run `skill cv --run <run>` first",
    "fit-before.json": "score the fit before tailoring first: "
                       "`skill fit --run <run> --when before`",
}


def require(run: Path, name: str) -> Path:
    """A file a verb cannot work without, or a sentence saying why not."""
    target = run / name
    if not target.exists():
        why = _NEEDED.get(name, f"{name} is missing from that run")
        raise FileNotFoundError(f"{run.name}: {why}.")
    return target


def write_json(run: Path, name: str, payload: object) -> Path:
    target = run / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    return target


def write_text(run: Path, name: str, text: str) -> Path:
    target = run / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    return target


def note(run: Path, label: str, url: str, base: Path | None = None) -> Path:
    """One line per run in runs/log.md, appended.

    The whole of what replaced application tracking. The run directory is the
    record; this is the index, and it is markdown so a rejection or an
    interview date can be typed straight into it.
    """
    log = paths.log_path(base)
    log.parent.mkdir(parents=True, exist_ok=True)
    if not log.exists():
        log.write_text("# Applications\n\n"
                       "One line per job prepared. Add what happened next yourself.\n\n",
                       encoding="utf-8")
    day = datetime.now(UTC).date().isoformat()
    line = f"- {day}  {label}  <{url}>  `{run.name}`\n"
    if line not in log.read_text(encoding="utf-8"):
        with log.open("a", encoding="utf-8") as handle:
            handle.write(line)
    return log
