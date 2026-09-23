"""Assemble the tailored CV from Claude's selection and the profile's facts."""

from __future__ import annotations

import yaml

from ... import render
from ...generate import cv as cv_module
from ...generate.parsing import parse_json
from ...jobs import models as job_models
from ...profile import store as profile_store
from .. import exits, runs


def add_arguments(parser) -> None:
    parser.add_argument("--run", required=True)
    parser.add_argument("--selection", default="cv-selection.json")
    parser.add_argument("--theme", default="neutral", choices=sorted(render.THEMES))


def run(args) -> int:
    from ..__main__ import emit

    run_dir = runs.resolve(args.run)
    data = parse_json(runs.require(run_dir, args.selection).read_text(encoding="utf-8"),
                      hint="Write cv-selection.json again, as plain JSON.")
    job = job_models.from_dict(
        yaml.safe_load(runs.require(run_dir, "job.yaml").read_text(encoding="utf-8")) or {})
    profile = profile_store.load(profile_store.profile_path())

    # The model chose which roles and how the bullets read. Every employer,
    # title, date and degree is copied from the profile here, which is why a
    # fabricated employer cannot be expressed.
    document = cv_module.assemble(profile, job, data)
    (run_dir / "cv.yaml").write_text(
        yaml.safe_dump(document.model_dump(mode="json"), sort_keys=False,
                       allow_unicode=True, width=100), encoding="utf-8")

    # Markdown before the PDF, always. If rendering fails, a document a person
    # can send already exists - so there is never a gap for a model to fill by
    # writing the CV itself.
    runs.write_text(run_dir, "cv.md", render.to_markdown(document))

    issues = [i.model_dump(mode="json") for i in document.all_issues]
    blocking = [i for i in issues if i["severity"] == "blocking"]
    pdf = None
    if not blocking:
        try:
            pdf = str(render.export(document, run_dir / "cv.pdf",
                                    theme=render.resolve(args.theme)))
        except render.PdfError as exc:
            print(f"The markdown is written; the PDF is not: {exc}")

    emit({"run": str(run_dir), "issues": issues, "blocking": blocking,
          "markdown": str(run_dir / "cv.md"), "pdf": pdf})
    for issue in issues:
        print(f"  [{issue['severity'][:4]}] {issue['path']}: {issue['message']}")
    return exits.UNFIT if blocking else exits.OK
