"""Score the CV against the job, before tailoring and after."""

from __future__ import annotations

import yaml

from ...fit import report as fit_report
from ...generate import cv as cv_module
from ...jobs import models as job_models
from ...profile import store as profile_store
from .. import exits, runs


def add_arguments(parser) -> None:
    parser.add_argument("--run", required=True)
    parser.add_argument("--when", choices=("before", "after"), required=True)
    parser.add_argument("--skim-bullets", type=int, default=fit_report.SKIM_BULLETS)


def _load_job(run_dir):
    return job_models.from_dict(
        yaml.safe_load((run_dir / "job.yaml").read_text(encoding="utf-8")) or {})


def run(args) -> int:
    from ..__main__ import emit

    run_dir = runs.resolve(args.run)
    job = _load_job(run_dir)
    profile = profile_store.load(profile_store.profile_path())

    document = None
    if args.when == "after":
        raw = yaml.safe_load((run_dir / "cv.yaml").read_text(encoding="utf-8")) or {}
        document = cv_module.TailoredCV.model_validate(raw)

    # Evidence is looked up in the profile in both arms, so `evidenced` cannot
    # differ between them. That is what makes the after-score unparrotable.
    found = fit_report.score(job, profile, document, when=args.when,
                             skim_bullets=args.skim_bullets)
    runs.write_json(run_dir, f"fit-{args.when}.json", found.model_dump(mode="json"))

    written = ""
    if args.when == "after":
        before_raw = (run_dir / "fit-before.json").read_text(encoding="utf-8")
        before = fit_report.FitReport.model_validate_json(before_raw)
        written = fit_report.delta(before, found)
        runs.write_text(run_dir, "fit-after.md", written)
    else:
        written = fit_report.delta(found, found)
        runs.write_text(run_dir, "fit-before.md", written)

    emit({"run": str(run_dir), "when": args.when,
          "evidenced": found.evidenced, "checkable": len(found.checkable),
          "shown": found.shown, "present": found.present,
          "gaps": found.gaps, "parroting": found.parroting,
          "regressions": found.regressions})
    print(written)
    return exits.OK
