#!/usr/bin/env python3
"""Score a CV on its own, with no job description.

The fit score answers "does this answer THIS posting" and needs a posting.
This answers the other question - "is this CV well built at all" - and needs
nothing but the profile.

Everything it measures is job-independent on purpose: a reader stops early
whatever the job, a figure is more convincing than an adjective whatever the
job, and a skill nobody can see you use is a claim whatever the job.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import jobhunt as jh  # noqa: E402


def work(argv):
    parser = argparse.ArgumentParser(prog="review", description=__doc__)
    parser.add_argument("--profile", help="profile.yaml to review")
    parser.add_argument("--run", help="a run to write review.md into")
    parser.add_argument("--json", action="store_true",
                        help="print the full breakdown as JSON")
    args = parser.parse_args(argv)

    path = Path(args.profile) if args.profile else jh.profile_path()
    profile = jh.load(jh.Profile, path)
    if not profile.experience and not profile.education:
        print(f"No profile at {path}. Build one first.", file=sys.stderr)
        return jh.BLOCKED

    found = jh.review(profile)
    page = jh.review_page(found)

    if args.run:
        run = jh.run_dir(args.run)
        jh.write_text(run, "review.md", page)

    summary = {
        "profile": str(path),
        "score": found.score, "out_of": found.out_of,
        "verdict": jh.band(found.score, found.out_of),
        "roles": found.roles, "bullets": found.bullets,
        "dimensions": [{"name": d.name, "points": d.points, "out_of": d.out_of,
                        "tally": d.tally} for d in found.dimensions],
    }
    if args.json:
        summary["findings"] = [{"where": f.where, "what": f.what, "quote": f.quote}
                               for f in found.findings]
    jh.emit(summary)
    print(page, file=sys.stderr)
    return jh.OK


if __name__ == "__main__":
    raise SystemExit(jh.run_cli(work))
