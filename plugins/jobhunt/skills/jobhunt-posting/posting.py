#!/usr/bin/env python3
"""Load a job posting, and turn the agent's reading of it into job.yaml.

Two steps, because only one of them needs judgement. `--fetch` loads the page
in the browser already on the machine and writes its text; `--parse` takes the
JSON the agent wrote from that text and stores it as a posting.

A page that comes back thin - a login wall, a spinner - stops here. Working
around a login wall means inventing a job description, which is the one failure
this whole tool exists to prevent.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import jobhunt as jh  # noqa: E402


def work(argv):
    parser = argparse.ArgumentParser(prog="posting", description=__doc__)
    parser.add_argument("url", nargs="?", help="the posting to load")
    parser.add_argument("--text", help="a file of pasted description text instead")
    parser.add_argument("--parse", metavar="JSON",
                        help="the JSON you wrote from the page text")
    parser.add_argument("--run", help="the run directory to work in")
    args = parser.parse_args(argv)

    if args.parse:
        return _parse(args)

    if args.text:
        body = Path(args.text).read_text(encoding="utf-8")
        url = args.url or ""
        jh.check_posting(url or args.text, body)
        page = jh.PageSource(url=url, text=body)
    elif args.url:
        page = jh.fetch(args.url)
    else:
        parser.error("give a URL, or --text with a file of pasted description")

    run = jh.run_dir(args.run) if args.run else jh.incoming(page.url or "pasted")
    run.mkdir(parents=True, exist_ok=True)
    jh.write_text(run, "page.txt", jh.trim(page.text))
    # What we observed, kept beside the text so --parse does not have to be
    # told again - and so the model's guess at the URL never wins over the
    # address we actually loaded.
    jh.write_json(run, "source.json", jh.asdict(page))

    jh.emit({"run": str(run), "url": page.url, "title": page.title,
             "brand_color": page.brand_color, "text_chars": len(page.text),
             "next": "read page.txt and write the posting as JSON, then --parse it"})
    return jh.OK


def _parse(args):
    """Store what the agent read off the page, with the facts we know kept."""
    if not args.run:
        raise ValueError("--parse needs --run")
    run = jh.run_dir(args.run)
    raw = jh.parse_json(Path(args.parse).read_text(encoding="utf-8"),
                        hint="Write the posting again, as plain JSON.")

    page = jh.require(run, "page.txt").read_text(encoding="utf-8")
    source = jh.build(jh.PageSource, jh.read_json(run, "source.json"))
    # The URL, the brand colour and the fetch time are things we observed. A
    # model only guesses at them, so what we know wins.
    job = jh.build(jh.Job, raw, url=source.url, source_text=page,
                   brand_color=source.brand_color or raw.get("brand_color", ""),
                   fetched_at=jh.now())

    missing = job.missing()
    if missing:
        print(missing, file=sys.stderr)
        return jh.BLOCKED

    jh.save(job, run / "job.yaml")
    # A fetch lands under a hash of the URL, because nothing knows what the job
    # is called yet. Now that it has been read, it gets its real name.
    settled = jh.promote(run, job.slug) if jh.is_incoming(run) else run
    jh.note(settled, job.label, job.url)

    jh.emit({"run": str(settled), "label": job.label, "slug": job.slug,
             "requirements": len(job.requirements),
             "nice_to_have": len(job.nice_to_have), "language": job.language,
             "brand_color": job.brand_color})
    return jh.OK


if __name__ == "__main__":
    raise SystemExit(jh.run_cli(work))
