#!/usr/bin/env python3
"""Check a piece of writing against the facts in a profile.

Lexical, not semantic: it compares the words and figures in the text against
the words and figures in the profile. It therefore misses a plausible-sounding
rewording and occasionally flags something legitimate. It is a review aid, and
every finding is addressed to the person about to send the document - it never
rewrites anything.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import jobhunt as jh  # noqa: E402


def work(argv):
    parser = argparse.ArgumentParser(prog="guard", description=__doc__)
    parser.add_argument("text", nargs="?",
                        help="the text to check; omit to read stdin")
    parser.add_argument("--file", help="read the text from this file instead")
    parser.add_argument("--profile", help="profile.yaml to check against")
    parser.add_argument("--language", default="",
                        help="the language the text is written in, e.g. fr")
    parser.add_argument("--asked", default="",
                        help="the question being answered, if it is an answer")
    parser.add_argument("--allow", default="",
                        help="extra words that are fair to use, comma separated "
                             "(the company and role, normally)")
    args = parser.parse_args(argv)

    if args.file:
        body = Path(args.file).read_text(encoding="utf-8")
    elif args.text:
        body = args.text
    else:
        body = sys.stdin.read()

    path = Path(args.profile) if args.profile else jh.profile_path()
    profile = jh.load(jh.Profile, path)
    if not profile.personal.full_name and not profile.experience:
        print(f"No profile at {path} - there is nothing to check against.",
              file=sys.stderr)
        return jh.BLOCKED

    support = jh.Support.of(profile)
    if args.allow:
        support = support | jh.Support.of(*[w.strip() for w in args.allow.split(",")])
    # A question's own words are unsupported but unavoidable: answering "no, I
    # have not used Workday" has to write Workday. Flagged, worded differently.
    asked = jh.Support.wording_of(args.asked) if args.asked else None

    issues = jh.check(body, support, "text", asked=asked, language=args.language)
    jh.emit({"profile": str(path), "checked_chars": len(body),
             "findings": [i.message for i in issues],
             "wording_checked": jh.reads(body, args.language)})
    for issue in issues:
        print(issue.message, file=sys.stderr)
    if not issues:
        print("Nothing in this is unsupported by the profile.", file=sys.stderr)
    return jh.OK


if __name__ == "__main__":
    raise SystemExit(jh.run_cli(work))
