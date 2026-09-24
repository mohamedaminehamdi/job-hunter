#!/usr/bin/env python3
"""Gather everything a critique should be based on, and file the verdict.

The reading is the agent's - this collects what it has to read, so the critique
is written against the documents and the score rather than from memory, and
lands in the run directory next to what it is about.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import jobhunt as jh  # noqa: E402


def work(argv):
    parser = argparse.ArgumentParser(prog="critique", description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--write", metavar="FILE",
                        help="the critique you wrote, as markdown")
    args = parser.parse_args(argv)

    run = jh.run_dir(args.run)

    if args.write:
        body = Path(args.write).read_text(encoding="utf-8")
        jh.write_text(run, "critique.md", body)
        jh.emit({"run": str(run), "critique": str(run / "critique.md"),
                 "chars": len(body)})
        return jh.OK

    job = jh.load(jh.Job, jh.require(run, "job.yaml"))
    cv = jh.load(jh.TailoredCV, run / "cv.yaml")
    letter = jh.load(jh.CoverLetter, run / "letter.yaml")

    print("=== The posting ===\n")
    print(job.brief())
    print("\n=== The CV as it stands ===\n")
    print(jh.to_markdown(cv))
    if letter.paragraphs:
        print("\n=== The letter ===\n")
        print(letter.body)
    for name in ("fit-after.md", "fit-before.md"):
        if (run / name).exists():
            print(f"\n=== {name} ===\n")
            print((run / name).read_text(encoding="utf-8"))
            break

    issues = [f"{i.path}: {i.message}" for i in (*cv.all_issues, *letter.all_issues)]
    jh.emit({"run": str(run), "has_cv": bool(cv.experience),
             "has_letter": bool(letter.paragraphs), "open_issues": issues,
             "next": "write the critique and file it with --write"})
    return jh.OK


if __name__ == "__main__":
    raise SystemExit(jh.run_cli(work))
