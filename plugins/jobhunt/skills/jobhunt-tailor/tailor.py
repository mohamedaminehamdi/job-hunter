#!/usr/bin/env python3
"""Build a CV for one job out of the facts already in the profile.

The agent never writes an employer, a job title, a date, a degree or a
certification. It answers with *indices* into the profile and reworded bullet
text, and everything else is copied across here - so a fabricated employer is
not something caught afterwards, it cannot be expressed.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import jobhunt as jh  # noqa: E402


def work(argv):
    parser = argparse.ArgumentParser(prog="tailor", description=__doc__)
    parser.add_argument("selection", nargs="?",
                        help="the JSON you wrote: summary, roles, projects, skills")
    parser.add_argument("--run", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--brief", action="store_true",
                        help="print the profile and the job as a prompt block "
                             "and stop - this is what you write the JSON from")
    parser.add_argument("--coach", action="store_true",
                        help="print, per bullet, what a reader will miss and the question "
                             "whose answer fixes it - ask the person before you tailor")
    args = parser.parse_args(argv)
    # The brief comes before there is a selection to give, so the positional
    # cannot be required: it used to be, and the skill had to be run with a
    # dummy "x" on the end to read it.
    if not (args.brief or args.coach) and not args.selection:
        parser.error("give the selection JSON you wrote, or --brief to read "
                     "the profile and the posting first, or --coach")

    run = jh.run_dir(args.run)
    job = jh.load(jh.Job, jh.require(run, "job.yaml"))
    profile = jh.load(jh.Profile, args.profile or jh.profile_path())

    if args.coach:
        page = jh.coaching(profile)
        print(page)
        bullets = sum(len(r.bullets) for r in profile.experience)
        without = sum(1 for r in profile.experience for b in r.bullets
                      if not jh.is_quantified(b))
        jh.emit({"run": str(run), "bullets": bullets, "without_figure": without,
                 "next": "ask the person each question, put the answers in profile.yaml, "
                         "then --brief"})
        return jh.OK

    if args.brief:
        print(jh.profile_block(profile))
        print("\n---\n")
        print(job.brief())
        jh.emit({"run": str(run), "roles": len(profile.experience),
                 "projects": len(profile.projects),
                 "next": "choose roles by index and reword their bullets"})
        return jh.OK

    raw = jh.parse_json(Path(args.selection).read_text(encoding="utf-8"),
                        hint="Write the selection again, as plain JSON.")
    document = jh.tailor(profile, job, raw)
    jh.save(document, run / "cv.yaml")

    issues = document.all_issues
    jh.emit({"run": str(run), "cv": str(run / "cv.yaml"),
             "roles": len(document.experience), "skills": len(document.skills),
             "blocking": [f"{i.path}: {i.message}" for i in document.blocking],
             "issues": [f"{i.path}: {i.message}" for i in issues]})
    for issue in issues:
        print(issue, file=sys.stderr)
    return jh.UNFIT if document.blocking else jh.OK


if __name__ == "__main__":
    raise SystemExit(jh.run_cli(work))
