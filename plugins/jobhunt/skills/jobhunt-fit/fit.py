#!/usr/bin/env python3
"""Score a CV against a posting - before tailoring, and after.

Two numbers, because they answer different questions and only one of them can
move. **Evidenced** is how much of what the job asks for the profile can back;
it is a fact about the candidate and it does not change when the CV is
rewritten. **Shown** is how much of that a reader meets in the first screenful,
and that is the one tailoring moves.

Evidence is looked up in the profile in both arms, never in the document, so a
CV that pastes the posting's words into its summary scores nothing extra and is
told off for it.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import jobhunt as jh  # noqa: E402


def work(argv):
    parser = argparse.ArgumentParser(prog="fit", description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--when", choices=("before", "after"), default="before")
    parser.add_argument("--profile", help="profile.yaml to measure against")
    parser.add_argument("--skim-bullets", type=int, default=jh.SKIM_BULLETS,
                        help="how many bullets a reader sees before deciding")
    args = parser.parse_args(argv)

    run = jh.run_dir(args.run)
    job = jh.load(jh.Job, jh.require(run, "job.yaml"))
    profile = jh.load(jh.Profile, args.profile or jh.profile_path())

    document = None
    if args.when == "after":
        document = jh.load(jh.TailoredCV, jh.require(run, "cv.yaml"))

    found = jh.score(job, profile, document, when=args.when,
                     skim_bullets=args.skim_bullets)
    jh.write_json(run, f"fit-{args.when}.json", jh.asdict(found))

    if args.when == "after":
        before = jh.build(jh.FitReport, jh.read_json(run, "fit-before.json"))
        written = jh.delta(before, found)
    else:
        written = jh.delta(found, found)
    jh.write_text(run, f"fit-{args.when}.md", written)

    jh.emit({"run": str(run), "when": args.when, "basis": found.basis,
             "evidenced": found.evidenced, "checkable": len(found.checkable),
             "shown": found.shown, "present": found.present,
             "gaps": found.gaps, "parroting": found.parroting,
             "regressions": found.regressions})
    print(written, file=sys.stderr)
    return jh.OK


if __name__ == "__main__":
    raise SystemExit(jh.run_cli(work))
