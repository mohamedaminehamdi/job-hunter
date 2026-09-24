#!/usr/bin/env python3
"""Write the cover letter, with the contact block copied from the profile.

Harder to hold the line on than the CV: a letter is where a model most wants to
help by calling the candidate "deeply experienced in" whatever the posting
asked for. So the body is checked word by word against the profile, and the job
contributes only its own name, role and location to the allowed vocabulary -
never its list of requirements.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import jobhunt as jh  # noqa: E402


def work(argv):
    parser = argparse.ArgumentParser(prog="letter", description=__doc__)
    parser.add_argument("draft", help="the JSON you wrote: greeting, paragraphs, "
                                      "closing")
    parser.add_argument("--run", required=True)
    parser.add_argument("--profile")
    args = parser.parse_args(argv)

    run = jh.run_dir(args.run)
    job = jh.load(jh.Job, jh.require(run, "job.yaml"))
    profile = jh.load(jh.Profile, args.profile or jh.profile_path())

    raw = jh.parse_json(Path(args.draft).read_text(encoding="utf-8"),
                        hint="Write the letter again, as plain JSON.")
    letter = jh.write_letter(profile, job, raw)
    jh.save(letter, run / "letter.yaml")

    issues = letter.all_issues
    jh.emit({"run": str(run), "letter": str(run / "letter.yaml"),
             "paragraphs": len(letter.paragraphs), "language": letter.language,
             "blocking": [f"{i.path}: {i.message}" for i in letter.blocking],
             "issues": [f"{i.path}: {i.message}" for i in issues]})
    for issue in issues:
        print(issue, file=sys.stderr)
    return jh.UNFIT if letter.blocking else jh.OK


if __name__ == "__main__":
    raise SystemExit(jh.run_cli(work))
