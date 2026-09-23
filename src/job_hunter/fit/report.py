"""Measuring one CV against one job, twice.

Two numbers, because they answer different questions and only one of them can
move:

* **evidenced** - of what the posting asks for, how much can the *profile* back?
  A fact about the candidate. Identical before and after tailoring, by
  construction: evidence is looked up in the profile, and rewriting a document
  cannot add to it.
* **shown** - of what the profile can back, how much does the *document* put in
  front of a reader in the first screenful? This is the one tailoring moves, and
  it is what tailoring is for.

Copying a requirement's words into a summary therefore earns nothing. It earns a
line in `parroting` instead, which is the tripwire for exactly that.

No single 0-100 score, deliberately. One number invites optimising the number,
and optimising this one means parroting. Counts, named, disjoint.
"""

from __future__ import annotations

from ..generate.guard import Support, norm
from ..jobs.models import Job
from ..profile.models import Profile
from . import evidence as ev
from . import requirements as req
from .models import EVIDENCED, NOT_CHECKABLE, NOT_EVIDENCED, FitReport, Requirement

#: What a reader meets before deciding to keep reading. Evidence below this is
#: in the document but not doing any work.
SKIM_BULLETS = 10


def _skim(document: Profile, bullets: int) -> str:
    """The first screenful: who they are, what they claim, the opening bullets."""
    parts = [document.personal.headline, document.summary, " ".join(document.skills)]
    seen = 0
    for role in document.experience:
        parts.append(f"{role.position} {role.company}")
        for bullet in role.bullets:
            if seen >= bullets:
                break
            parts.append(bullet)
            seen += 1
    return "\n".join(p for p in parts if p)


def _everything(document: Profile) -> str:
    """Every word of the document, for telling 'buried' from 'absent'."""
    parts = [document.personal.headline, document.summary, " ".join(document.skills)]
    for role in document.experience:
        parts += [role.position, role.company, role.industry, *role.bullets, *role.skills]
    for project in document.projects:
        parts += [project.name, project.description, *project.tech]
    for education in document.education:
        parts += [education.level, education.field_of_study, education.institution,
                  *education.courses]
    for cert in document.certifications:
        parts += [cert.name, cert.issuer, cert.description]
    for language in document.languages:
        parts += [language.name, language.level]
    return "\n".join(p for p in parts if p)


def score(job: Job, profile: Profile, document: Profile | None = None, *,
          when: str = "before", skim_bullets: int = SKIM_BULLETS) -> FitReport:
    """Measure `document` against `job`, with `profile` as the only source of evidence.

    `document` defaults to the profile itself, which is what "before" means: the
    CV as it stands. Passing a `TailoredCV` gives "after". Both arms run the
    same code and look evidence up in the same place, so `evidenced` cannot
    differ between them - that is a property of the design, not of care.
    """
    document = document if document is not None else profile
    support = Support.of(profile)
    # A lowercase tool the candidate actually lists - dbt, npm - is a name, not
    # an ordinary word. Nothing here comes from the job: the posting never gets
    # to widen what counts as evidence.
    vocabulary = frozenset(norm(skill) for skill in ev.skills_index(profile))
    skim, whole = _skim(document, skim_bullets), _everything(document)

    parroting: list[str] = []
    regressions: list[str] = []
    gaps: list[str] = []

    found: list[Requirement] = []
    for requirement in req.extract(job, vocabulary):
        if not requirement.terms:
            found.append(requirement)
            continue

        backed, missing, evidence = [], [], []
        for term in requirement.terms:
            hits = ev.find(term, profile, support=support)
            if hits:
                backed.append(term)
                evidence.append(hits[0])
            else:
                missing.append(term)

        # One backed term is enough. Requirement lines bundle several things -
        # "Python or Go", "Kubernetes and Docker" - and extraction is lexical,
        # so demanding all of them would report noise as a gap.
        status = EVIDENCED if backed else NOT_EVIDENCED
        requirement = requirement.model_copy(update={
            "status": status,
            "missing": missing,
            "evidence": evidence,
            "shown_in_skim": bool(ev.mentions_any(skim, backed)),
            "present_anywhere": bool(ev.mentions_any(whole, backed)),
        })
        found.append(requirement)

        if status == NOT_EVIDENCED and requirement.kind == "required":
            gaps.extend(requirement.terms)
            # Named in the document, backed by nothing. The document is
            # repeating the posting rather than the candidate.
            parroting.extend(ev.mentions_any(whole, requirement.terms))
        elif backed and not ev.mentions_any(whole, backed):
            # The profile can back this and the document dropped it entirely.
            regressions.extend(backed)

    return FitReport(
        when=when,
        job_label=job.label,
        job_url=job.url,
        basis=req.basis_of(job),
        skim_bullets=skim_bullets,
        requirements=found,
        parroting=sorted(set(parroting)),
        regressions=sorted(set(regressions)),
        gaps=sorted(set(gaps)),
        years_note=_years_note(job, profile),
    )


def _years_note(job: Job, profile: Profile) -> str:
    """What the posting asks for in years against what the profile can date.

    The one gap tailoring can never close, and it is on nearly every posting a
    student reads. An unreadable date is not a short career, so silence when the
    profile cannot be dated.
    """
    asked = max((y for line in job.requirements
                 if (y := req.years_required(line)) is not None), default=None)
    if asked is None:
        return ""
    held = req.years_held(profile)
    if held is None:
        return f"Asks for {asked} years. Your roles carry no readable dates."
    if held >= asked:
        return f"Asks for {asked} years; your profile dates to about {held:.0f}."
    return (f"Asks for {asked} years; your profile dates to about {held:.0f}. "
            "This is the gap tailoring cannot close.")


def delta(before: FitReport, after: FitReport) -> str:
    """What tailoring bought, in one block a person can read."""
    checkable = len(before.checkable)
    lines = [
        f"Fit for {before.job_label}",
        "",
        f"Evidenced in your profile:    {before.evidenced} of {checkable}"
        "   (unchanged by tailoring - it is what you have done)",
    ]
    if not_checkable := before.count(NOT_CHECKABLE):
        lines.append(f"  not checkable:              {not_checkable}"
                     "        (judge these yourself)")

    backed = before.evidenced
    lines += [
        "",
        f"Shown in the first screenful: {before.shown} of {backed}"
        f"  ->  {after.shown} of {backed}"
        f"      {after.shown - before.shown:+d}",
        f"Present anywhere in the CV:   {before.present} of {backed}"
        f"  ->  {after.present} of {backed}",
    ]
    if after.regressions:
        lines.append(f"  ! left off entirely: {', '.join(after.regressions)}")
    if after.parroting:
        lines.append("")
        lines.append(f"  ! claimed but not evidenced: {', '.join(after.parroting)}"
                     "  - the CV names these and your profile does not back them")
    if after.gaps:
        lines += ["", "Not evidenced anywhere in your profile:"]
        for requirement in after.required:
            if requirement.status == NOT_EVIDENCED:
                lines.append(f"  · {', '.join(requirement.terms):<28} "
                             f"\"{requirement.text[:60]}\"")
    if after.years_note:
        lines += ["", f"  · {after.years_note}"]
    return "\n".join(lines)
