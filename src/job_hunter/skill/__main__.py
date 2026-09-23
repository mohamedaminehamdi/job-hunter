"""The one thing the skill is allowed to run.

    python -m job_hunter.skill <verb> [options]

Every verb reads files, writes files into a run directory, prints one line of
JSON, and exits with a code from `exits`. Nothing here decides anything a person
would call judgement - that is the skill's half. What lives on this side is
everything that must come out the same way twice: validation, the invention
guard, the fit score, URL building, and rendering.

One dispatcher rather than a script per verb so the permission allowlist is a
single entry and the exit codes are defined in one place.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from ..generate.errors import GenerationError
from ..generate.parsing import ParseError
from ..jobs.fetch import FetchError
from ..profile.intake import IntakeError
from ..render import ExportBlocked, PdfError
from . import exits
from .verbs import cv, doctor, fetch, fit, job, letter, outreach, profile, report

VERBS = {
    "doctor": doctor, "profile": profile, "fetch": fetch, "job": job,
    "fit": fit, "cv": cv, "letter": letter, "outreach": outreach, "report": report,
}

#: Everything the library raises on purpose. All carry a message for a person.
USER_ERRORS = (IntakeError, FetchError, GenerationError, ParseError,
               ExportBlocked, PdfError, ValueError, FileNotFoundError)


def emit(payload: dict[str, Any]) -> None:
    """One line of JSON on stdout. The skill reads this; a person reads stderr."""
    print(json.dumps(payload, ensure_ascii=False, default=str))


def fail(message: str, code: int = exits.BLOCKED) -> int:
    print(message, file=sys.stderr)
    return code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m job_hunter.skill",
        description="The deterministic half of the prep-apply skill.",
    )
    sub = parser.add_subparsers(dest="verb", required=True)
    for name, module in VERBS.items():
        module.add_arguments(sub.add_parser(name, help=module.__doc__.splitlines()[0]))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return VERBS[args.verb].run(args)
    except ParseError as exc:
        return fail(str(exc), exits.UNREADABLE)
    except (ExportBlocked, PdfError) as exc:
        return fail(str(exc), exits.UNFIT)
    except USER_ERRORS as exc:
        return fail(str(exc), exits.BLOCKED)
    except KeyboardInterrupt:  # pragma: no cover
        return fail("interrupted", exits.BLOCKED)


if __name__ == "__main__":
    raise SystemExit(main())
