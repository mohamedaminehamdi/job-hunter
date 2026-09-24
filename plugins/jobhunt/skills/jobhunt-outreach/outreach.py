#!/usr/bin/env python3
"""Work out who is worth messaging, build the searches, check the draft.

It does not scrape LinkedIn. LinkedIn walls and throttles automated access, and
the risk of working around that lands on your account, not on this repo.

The agent names job titles. **Every URL is built here**, so a malformed or
hostile link cannot come out of its JSON - the same structural rule the CV
follows. You run the search and press send.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import jobhunt as jh  # noqa: E402


def work(argv):
    parser = argparse.ArgumentParser(prog="outreach", description=__doc__)
    parser.add_argument("plan", help="the JSON you wrote: targets, message")
    parser.add_argument("--run", required=True)
    parser.add_argument("--profile")
    args = parser.parse_args(argv)

    run = jh.run_dir(args.run)
    job = jh.load(jh.Job, jh.require(run, "job.yaml"))
    profile = jh.load(jh.Profile, args.profile or jh.profile_path())

    raw = jh.parse_json(Path(args.plan).read_text(encoding="utf-8"),
                        hint="Write the outreach plan again, as plain JSON.")
    plan = jh.plan_outreach(raw, profile, job)
    jh.write_text(run, "outreach.md", jh.outreach_page(plan))

    over = plan.over_limit()
    jh.emit({"run": str(run), "page": str(run / "outreach.md"),
             "targets": len(plan.targets), "issues": plan.issues,
             "over_limit": over, "note_chars": len(plan.message.note),
             "inmail_words": len(plan.message.inmail.split())})
    for line in [*over, *plan.issues]:
        print(line, file=sys.stderr)
    return jh.UNFIT if over else jh.OK


if __name__ == "__main__":
    raise SystemExit(jh.run_cli(work))
