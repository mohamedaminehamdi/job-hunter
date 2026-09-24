"""Build the LinkedIn searches and check the message Claude drafted."""

from __future__ import annotations

import yaml

from ...generate import guard
from ...generate.parsing import parse_json
from ...jobs import models as job_models
from ...outreach import links, models, render
from ...profile import store as profile_store
from .. import exits, runs


def add_arguments(parser) -> None:
    parser.add_argument("--run", required=True)
    parser.add_argument("--plan", default="outreach.json")


def run(args) -> int:
    from ..__main__ import emit

    run_dir = runs.resolve(args.run)
    raw = parse_json(runs.require(run_dir, args.plan).read_text(encoding="utf-8"),
                     hint="Write outreach.json again, as plain JSON.")
    job = job_models.from_dict(
        yaml.safe_load(runs.require(run_dir, "job.yaml").read_text(encoding="utf-8")) or {})
    profile = profile_store.load(profile_store.profile_path())

    schools = [e.institution for e in profile.education if e.institution]
    slug = links.company_slug(job.source_text)

    targets = []
    for entry in raw.get("targets") or []:
        tier = str(entry.get("tier", models.PEER))
        title = str(entry.get("title", "")).strip()
        if not title and tier != models.ALUMNI:
            continue
        # Claude names the role; the URL is built here, so a malformed or
        # hostile link cannot come out of a model's JSON.
        if tier == models.ALUMNI:
            url = links.alumni_search(schools[0] if schools else "", job.company)
            title = title or (schools[0] if schools else "Your university")
        elif slug:
            url = links.company_people(slug, keywords=title)
        else:
            url = links.people_search(title, job.company)
        targets.append(models.Target(tier=tier, title=title,
                                     why=str(entry.get("why", "")), search_url=url))

    drafted = raw.get("message") or {}
    message = models.Message(
        subject=str(drafted.get("subject", "")).strip(),
        note=str(drafted.get("note", "")).strip(),
        inmail=str(drafted.get("inmail", "")).strip(),
    )

    # The one piece of free text nobody guarded before. Same widening as the
    # letter: the company and the role may be named, the job's requirements
    # may not be claimed.
    support = guard.Support.of(profile) | guard.Support.of(job.company, job.title)
    issues = [i.message for i in
              guard.check_all({"note": message.note, "inmail": message.inmail},
                              support, language=job.language)]

    over = []
    if len(message.note) > models.NOTE_CHARS:
        over.append(f"The connection note is {len(message.note)} characters; "
                    f"LinkedIn rejects anything over {models.NOTE_CHARS}.")
    if len(message.inmail.split()) > models.INMAIL_WORDS:
        over.append(f"The message is {len(message.inmail.split())} words; "
                    f"keep it under {models.INMAIL_WORDS}.")
    if len(message.subject) > models.SUBJECT_CHARS:
        over.append(f"The subject is {len(message.subject)} characters; "
                    f"keep it under {models.SUBJECT_CHARS}.")

    plan = models.Outreach(company=job.company, role=job.title, targets=targets,
                           message=message, issues=issues)
    runs.write_text(run_dir, "outreach.md", render.page(plan))

    emit({"run": str(run_dir), "targets": len(targets), "issues": issues,
          "over_limit": over, "note_chars": len(message.note),
          "inmail_words": len(message.inmail.split())})
    for line in [*over, *issues]:
        print(line)
    return exits.UNFIT if over else exits.OK
