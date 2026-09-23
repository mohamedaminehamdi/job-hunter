"""Write the run's index, and add a line to the log."""

from __future__ import annotations

import json

import yaml

from ...jobs import models as job_models
from .. import exits, runs

#: What a finished run holds, in the order a person wants it.
ARTEFACTS = [
    ("cv.pdf", "Tailored CV, ready to attach"),
    ("cv.md", "The same CV as text, to paste into a form"),
    ("letter.pdf", "Cover letter"),
    ("letter.md", "The same letter as text"),
    ("fit-before.md", "How your CV answered this job before tailoring"),
    ("fit-after.md", "And after"),
    ("outreach.md", "Who to message, and what to say"),
    ("critique.md", "What is weak in the drafts"),
    ("job.yaml", "The posting, as read"),
    ("page.txt", "The posting, as scraped"),
]


def add_arguments(parser) -> None:
    parser.add_argument("--run", required=True)


def run(args) -> int:
    from ..__main__ import emit

    run_dir = runs.resolve(args.run)
    job = job_models.from_dict(
        yaml.safe_load((run_dir / "job.yaml").read_text(encoding="utf-8")) or {})

    present = [(name, what) for name, what in ARTEFACTS if (run_dir / name).exists()]
    lines = [f"# {job.label}", "", f"<{job.url}>" if job.url else "", ""]
    lines += [f"- `{name}` — {what}" for name, what in present]

    issues: list[str] = []
    for name in ("fit-after.json", "fit-before.json"):
        if (run_dir / name).exists():
            found = json.loads((run_dir / name).read_text(encoding="utf-8"))
            if found.get("parroting"):
                issues.append("The CV names things your profile does not back: "
                              + ", ".join(found["parroting"]))
            if found.get("gaps"):
                issues.append("Asked for and not in your profile: "
                              + ", ".join(found["gaps"]))
            break
    if issues:
        lines += ["", "## Before you send", ""] + [f"- {i}" for i in issues]
    lines += ["", "Nothing here was sent. Applying is yours to do."]

    runs.write_text(run_dir, "README.md", "\n".join(lines))
    log = runs.note(run_dir, job.label, job.url)

    emit({"run": str(run_dir), "files": [name for name, _ in present],
          "log": str(log), "issues": issues})
    print(f"{job.label}\n{run_dir}")
    return exits.OK
