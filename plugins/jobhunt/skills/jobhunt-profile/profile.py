#!/usr/bin/env python3
"""Validate a profile, or print a CV's text so the agent can build one.

Reading somebody's CV layout is judgement, so this script does not attempt it.
It hands over the words, and the agent writes profile.yaml from them. What it
does own is everything that must come out the same way twice: the check, the
normalisation, and the report.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import jobhunt as jh  # noqa: E402


def work(argv):
    parser = argparse.ArgumentParser(prog="profile", description=__doc__)
    parser.add_argument("--cv", help="print the text of this CV file and stop")
    parser.add_argument("--normalise", action="store_true",
                        help="tidy the saved profile and report on it")
    parser.add_argument("--home", help="the jobhunt directory to work in")
    args = parser.parse_args(argv)

    base = Path(args.home) if args.home else jh.home()
    path = jh.profile_path(base)

    if args.cv:
        # Deliberately not parsed into a profile here: a model has to map these
        # words onto the schema, and that is the agent's half.
        print(jh.read_cv_text(args.cv))
        jh.emit({"source": str(args.cv), "profile": str(path),
                 "exists": path.exists(),
                 "next": "write profile.yaml from this text, then run --normalise"})
        return jh.OK

    profile = jh.load(jh.Profile, path)
    if args.normalise:
        profile = jh.restore_scheme(profile)
        jh.save(profile, path)

    issues = profile.report()
    jh.emit({
        "profile": str(path), "exists": path.exists(),
        "renderable": profile.is_renderable,
        "roles": len(profile.experience), "skills": len(profile.skills),
        "issues": [{"path": i.path, "severity": i.severity, "message": i.message}
                   for i in issues],
    })
    for issue in issues:
        print(issue, file=sys.stderr)
    if not path.exists():
        print(f"No profile at {path}. Put a CV in {jh.cv_dir(base)} and build one.",
              file=sys.stderr)
        return jh.BLOCKED
    return jh.OK if profile.is_renderable else jh.BLOCKED


if __name__ == "__main__":
    raise SystemExit(jh.run_cli(work))
