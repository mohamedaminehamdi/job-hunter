#!/usr/bin/env python3
"""List a careers board's openings, ranked by how many of your skills each names.

Greenhouse and Lever publish every board as public JSON, so this needs no
browser and no login and scrapes nothing. The ranking is lexical - which of
the profile's own listed skills a posting names - and is a filter for what is
worth reading properly, not a fit score. Nothing here applies to anything.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import jobhunt as jh  # noqa: E402


def work(argv):
    parser = argparse.ArgumentParser(prog="find", description=__doc__)
    parser.add_argument("boards", nargs="+",
                        help="greenhouse:<token>, lever:<token>, or a careers page URL")
    parser.add_argument("--title", default="",
                        help="keep only titles containing this, case-insensitive")
    parser.add_argument("--min", type=int, default=1,
                        help="how many of your skills a posting must name to be listed")
    parser.add_argument("--limit", type=int, default=50, help="how many to list")
    parser.add_argument("--profile", help="profile.yaml to rank against")
    args = parser.parse_args(argv)

    path = Path(args.profile) if args.profile else jh.profile_path()
    profile = jh.load(jh.Profile, path)
    if not profile.skills and not profile.experience:
        print(f"No profile at {path}. Build one first - the ranking is against your skills.",
              file=sys.stderr)
        return jh.BLOCKED

    boards, found = [], []
    for given in args.boards:
        # A bare token could be either host; the first that answers is the one.
        last = None
        for board in jh.parse_board(given):
            try:
                found += jh.openings(board)
            except jh.FetchError as exc:
                last = exc
                continue
            boards.append(board)
            break
        else:
            raise last

    if args.title:
        wanted = args.title.lower()
        found = [o for o in found if wanted in o.title.lower()]
    ranked = jh.leads(found, profile, at_least=args.min)[:args.limit]
    page = jh.leads_page(ranked, boards, len(found))

    where = jh.found_dir()
    stem = f"{jh.today()}-" + "-".join(b.token for b in boards)[:60]
    written = jh.write_text(where, f"{stem}.md", page)
    # The posting text stays in memory: the file is the list, not the postings.
    jh.write_json(where, f"{stem}.json",
                  [{**jh.asdict(lead), "opening": {**jh.asdict(lead.opening), "text": ""}}
                   for lead in ranked])

    jh.emit({"boards": [b.label for b in boards], "openings": len(found),
             "listed": len(ranked), "page": str(written),
             "top": [{"title": lead.opening.title, "url": lead.opening.url,
                      "names": lead.score} for lead in ranked[:5]],
             "next": "read the page with the person, then read the posting they pick"})
    print(page, file=sys.stderr)
    return jh.OK


if __name__ == "__main__":
    raise SystemExit(jh.run_cli(work))
