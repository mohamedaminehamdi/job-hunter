"""Load a job posting with a browser and keep the text."""

from __future__ import annotations

from ...jobs import fetch as fetch_module
from .. import exits, runs


def add_arguments(parser) -> None:
    parser.add_argument("url")
    parser.add_argument("--timeout", type=int, default=30)


def run(args) -> int:
    from ..__main__ import emit

    # A browser, not an HTTP request: every board worth reading renders its
    # description client-side, so a plain fetch gets a spinner.
    source = fetch_module.fetch(args.url, timeout=args.timeout)
    run_dir = runs.incoming(source.url)
    runs.write_text(run_dir, "page.txt", fetch_module.trim(source.text))
    runs.write_json(run_dir, "page.json", {
        "url": source.url, "title": source.title,
        "brand_color": source.brand_color, "text_chars": len(source.text),
    })
    emit({"run": str(run_dir), "url": source.url, "title": source.title,
          "text_chars": len(source.text)})
    return exits.OK
