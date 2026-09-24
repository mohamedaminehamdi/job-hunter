#!/usr/bin/env python3
"""Check an answer to an application question against the profile.

The questions that get lied to: "Do you have experience with X?", "Why do you
want to work here?". An honest no is a real answer and this is built to allow
one - so a question's own words are treated separately. Writing "Workday" is
unavoidable when saying you have never used Workday, and the finding says so
rather than telling you to remove the word.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import jobhunt as jh  # noqa: E402

#: Application forms cut answers off rather than refuse them, so a length that
#: is over is worth knowing before pasting, not after.
DEFAULT_LIMIT = 0


def work(argv):
    parser = argparse.ArgumentParser(prog="answer", description=__doc__)
    parser.add_argument("answer", nargs="?", help="your draft; omit to read stdin")
    parser.add_argument("--question", default="", required=False,
                        help="the question being answered")
    parser.add_argument("--file", help="read the answer from this file")
    parser.add_argument("--run", help="a run, so the company and role are fair game")
    parser.add_argument("--profile")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help="the form's character limit, if it states one")
    parser.add_argument("--language", default="")
    args = parser.parse_args(argv)

    if args.file:
        body = Path(args.file).read_text(encoding="utf-8")
    elif args.answer:
        body = args.answer
    else:
        body = sys.stdin.read()

    profile = jh.load(jh.Profile, args.profile or jh.profile_path())
    support = jh.Support.of(profile)
    language = args.language

    if args.run:
        run = jh.run_dir(args.run)
        job = jh.load(jh.Job, jh.require(run, "job.yaml"))
        # Naming the company and the role you are applying for is not a claim.
        support = support | jh.Support.of(job.company, job.title)
        language = language or job.language

    # The question's vocabulary stays unsupported - "yes, I have used X" must
    # still be flagged - but the finding is worded for a word you cannot avoid.
    asked = jh.Support.wording_of(args.question) if args.question else None
    issues = jh.check(body, support, "answer", asked=asked, language=language)

    over = []
    if args.limit and len(body) > args.limit:
        over.append(f"The answer is {len(body)} characters; the form allows "
                    f"{args.limit}. It will be cut off, not refused.")

    jh.emit({"chars": len(body), "words": len(body.split()),
             "findings": [i.message for i in issues], "over_limit": over,
             "wording_checked": jh.reads(body, language)})
    for line in [*over, *[i.message for i in issues]]:
        print(line, file=sys.stderr)
    if not issues and not over:
        print("Nothing in this answer is unsupported by your profile.",
              file=sys.stderr)
    return jh.UNFIT if over else jh.OK


if __name__ == "__main__":
    raise SystemExit(jh.run_cli(work))
