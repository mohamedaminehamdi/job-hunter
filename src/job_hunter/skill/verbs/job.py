"""Validate the posting Claude read, and give the run its real name."""

from __future__ import annotations

import json
import sys

import yaml

from ...generate.parsing import parse_json
from ...jobs import models as job_models
from .. import exits, runs


def add_arguments(parser) -> None:
    parser.add_argument("--run", required=True)
    parser.add_argument("--parsed", default="job.json",
                        help="the JSON Claude wrote, inside the run directory")


def run(args) -> int:
    from ..__main__ import emit

    run_dir = runs.resolve(args.run)
    raw = parse_json((run_dir / args.parsed).read_text(encoding="utf-8"),
                     hint="Write job.json again, as plain JSON.")

    page = {}
    if (page_file := run_dir / "page.json").exists():
        page = json.loads(page_file.read_text(encoding="utf-8"))
    text = (run_dir / "page.txt").read_text(encoding="utf-8") \
        if (run_dir / "page.txt").exists() else ""

    # What was actually observed beats what the model wrote about it. The URL
    # and the brand colour are facts we hold; they are not the model's to guess.
    job = job_models.from_dict(raw, url=page.get("url", ""),
                               brand_color=page.get("brand_color", ""),
                               source_text=text, fetched_at=job_models.now())

    settled = runs.promote(run_dir, job.slug)
    (settled / "job.yaml").write_text(
        yaml.safe_dump(job.model_dump(mode="json"), sort_keys=False,
                       allow_unicode=True, width=100), encoding="utf-8")

    problem = job.missing()
    emit({"run": str(settled), "slug": job.slug, "label": job.label,
          "usable": job.is_usable, "problem": problem,
          "requirements": len(job.requirements), "language": job.language})
    if problem:
        print(problem, file=sys.stderr)
        return exits.BLOCKED
    return exits.OK
