"""Assemble the cover letter from Claude's draft and the profile's facts."""

from __future__ import annotations

import yaml

from ... import render
from ...generate import cover_letter as letter_module
from ...generate.parsing import parse_json
from ...jobs import models as job_models
from ...profile import store as profile_store
from .. import exits, runs


def add_arguments(parser) -> None:
    parser.add_argument("--run", required=True)
    parser.add_argument("--draft", default="letter-draft.json")
    parser.add_argument("--theme", default="neutral", choices=sorted(render.THEMES))
    parser.add_argument("--branded", action="store_true",
                        help="use the colour read off the company's page")


def run(args) -> int:
    from ..__main__ import emit

    run_dir = runs.resolve(args.run)
    data = parse_json(runs.require(run_dir, args.draft).read_text(encoding="utf-8"),
                      hint="Write letter-draft.json again, as plain JSON.")
    job = job_models.from_dict(
        yaml.safe_load(runs.require(run_dir, "job.yaml").read_text(encoding="utf-8")) or {})
    profile = profile_store.load(profile_store.profile_path())

    # The model wrote the prose. The name, the contact details, the company and
    # the date are copied from the profile and the job, and every figure and
    # proper noun in the paragraphs is checked against the profile afterwards.
    document = letter_module.assemble(profile, job, data)
    (run_dir / "letter.yaml").write_text(
        yaml.safe_dump(document.model_dump(mode="json"), sort_keys=False,
                       allow_unicode=True, width=100), encoding="utf-8")

    # Markdown before the PDF, always, so a failed render still leaves something
    # sendable and no gap for a model to fill by writing the letter itself.
    runs.write_text(run_dir, "letter.md", render.to_markdown(document))

    issues = [i.model_dump(mode="json") for i in document.all_issues]
    blocking = [i for i in issues if i["severity"] == "blocking"]
    pdf = None
    if not blocking:
        try:
            theme = render.resolve(args.theme)
            if args.branded:
                theme = render.branded(job.brand_color, base=theme)
            pdf = str(render.export(document, run_dir / "letter.pdf", theme=theme))
        except render.PdfError as exc:
            print(f"The markdown is written; the PDF is not: {exc}")

    emit({"run": str(run_dir), "issues": issues, "blocking": blocking,
          "markdown": str(run_dir / "letter.md"), "pdf": pdf})
    for issue in issues:
        print(f"  [{issue['severity'][:4]}] {issue['path']}: {issue['message']}")
    return exits.UNFIT if blocking else exits.OK
