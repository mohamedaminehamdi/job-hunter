"""Read a CV's text, or check the profile built from it."""

from __future__ import annotations

from pathlib import Path

from ... import paths
from ...profile import intake
from ...profile import store as profile_store
from ...profile.models import Severity
from .. import exits

MARKS = {Severity.BLOCKING: "x", Severity.WARNING: "!", Severity.INFO: "-"}


def add_arguments(parser) -> None:
    parser.add_argument("--cv", help="a CV file to extract the text of")
    parser.add_argument("--check", action="store_true", help="report the saved profile")
    parser.add_argument("--normalise", action="store_true",
                        help="tidy the saved profile and report it")


def _report(profile) -> list:
    return profile.report()


def run(args) -> int:
    from ..__main__ import emit

    path = profile_store.profile_path()

    if args.cv:
        # Deterministic: the words out of the file, nothing more. Mapping them
        # onto the schema needs judgement, which is the skill's half.
        source = Path(args.cv)
        if not source.is_absolute():
            source = paths.cv_dir() / source.name
        print(intake.read_text(source))
        return exits.OK

    if args.normalise:
        profile = profile_store.load(path)
        # A printed CV shows "github.com/ada"; the scheme is dropped for print
        # and has to come back, or the check complains about a link that is fine.
        profile = intake.restore_scheme(profile)
        profile_store.save(profile, path)

    profile = profile_store.load(path)
    issues = _report(profile)
    blocking = [i for i in issues if i.severity is Severity.BLOCKING]
    emit({
        "profile": str(path),
        "exists": path.exists(),
        "name": profile.personal.full_name,
        "roles": len(profile.experience),
        "ready": not blocking and path.exists(),
        "issues": [i.model_dump(mode="json") for i in issues],
    })

    if not path.exists():
        print(f"No profile at {path}.")
        return exits.BLOCKED
    print(f"{profile.personal.full_name or '(no name)'} - "
          f"{len(profile.experience)} role(s), {len(profile.education)} degree(s)")
    for issue in issues:
        print(f"  [{MARKS[issue.severity]}] {issue.path}: {issue.message}")
    return exits.BLOCKED if blocking else exits.OK
