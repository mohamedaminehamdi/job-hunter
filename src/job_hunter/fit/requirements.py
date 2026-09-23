"""Turning a posting's requirement lines into things that can be looked for.

A requirement is a sentence. Some sentences name something concrete - a tool, a
language, a certificate - and those can be checked against a profile. Many do
not: "Strong communication skills", "Thrives in a fast-paced environment". A
lexical reader cannot judge those, and pretending otherwise is worse than
saying so, so they leave the denominator and are printed for the candidate to
judge.

Nothing here asks a model for anything. `Job.requirements` is already a list of
lines by the time it arrives.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from ..generate.guard import norm, words
from ..jobs.models import Job
from ..profile.models import Profile
from .models import Requirement

#: Words that carry no signal, ported from the search scorer this replaces.
_NOISE = frozenset("""
a an the and or of for to in at on with by from new our we you your job role
position opening opportunity career careers hiring m f d w x h
one two three four five six seven eight nine ten
du sie wir ihr der die das den dem ein eine einen als auch bei mit von und oder
le la les un une des du au aux et ou avec chez dans pour par
""".split())

#: The vocabulary requirements are written in, as opposed to what they require.
#: "Experience with Kafka" is about Kafka; every other word is scaffolding.
_SCAFFOLDING = frozenset("""
experience experienced strong solid proven deep good excellent working work
years year knowledge understanding familiarity familiar ability able skills
skill background track record hands-on plus bonus ideally preferably must have
has having is are be been you your we our team environment able comfortable
significant substantial extensive considerable relevant appropriate suitable
equivalent similar related various several multiple broad wide
demonstrated ausgezeichnete gute kenntnisse erfahrung jahre sowie expérience
connaissance solide maîtrise ans bonne
""".split())

#: HR vocabulary. A lexical reader cannot judge "strong communication skills",
#: and a profile is not going to contain the word "proactive". Treating these as
#: requirements would report them as gaps, which is noise dressed as rigour, so
#: a line that names nothing else is marked not checkable instead.
_SOFT = frozenset("""
communication communicator collaboration collaborative teamwork team-player
leadership ownership autonomy autonomous independent independently proactive
motivated driven passionate curious pragmatic organised organized reliable
detail-oriented analytical creative flexible adaptable resilient enthusiasm
mindset attitude fast-paced dynamic startup culture fit player self-starter
thrive thrives thriving excited excellent great strong deep passion interest
willing eager keen love enjoy comfortable confident
kommunikation teamfähigkeit selbstständig eigenverantwortlich
communication autonomie rigueur curiosité esprit équipe
""".split())

#: Postings write the number both ways, and "Five or more years" is as common
#: as "5+ years".
_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10,
    "un": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "sept": 7,
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7,
}
_YEARS = re.compile(
    rf"(\d+|{'|'.join(_WORD_NUMBERS)})\s*(?:\+|-\s*\d+)?\s*"
    r"(?:or more\s*)?(?:years?|yrs?|ans?|jahre[n]?)\b", re.IGNORECASE)

#: A role that has not ended.
_PRESENT = frozenset("present now current ongoing today heute aujourd'hui actuel".split())


def salient_terms(line: str, vocabulary: frozenset[str] = frozenset()) -> list[str]:
    """The concrete things a requirement line asks for, in order, deduplicated.

    Precision over recall, deliberately. A term is kept when it looks like a
    *name* rather than a word: an acronym, a capitalised word, or something
    carrying a digit or a symbol - AWS, Kubernetes, C++, CI/CD, Python3.

    `vocabulary` rescues the exception: plenty of real tools are lowercase -
    dbt, npm, kubectl - and would look like ordinary words. A token the
    candidate lists among their own skills is a name whatever its case.

    The cost is that a lowercase tool the candidate does *not* have is missed
    here. That is the right trade: a wrongly reported gap - telling someone they
    lack "production" - is worse than a quiet omission, because the
    requirement's own sentence is printed beside the verdict for them to read.
    """
    found: list[str] = []
    seen: set[str] = set()
    for word in words(line):
        key = norm(word)
        if len(word) < 2 or key in seen:
            continue
        if key in _NOISE or key in _SCAFFOLDING or key in _SOFT:
            continue
        named = (word.isupper() or word[0].isupper()
                 or any(c.isdigit() or c in "+#/." for c in word)
                 or key in vocabulary)
        if not named:
            continue
        seen.add(key)
        found.append(word)
    return found


def years_required(line: str) -> int | None:
    """How many years a line asks for, when it asks in a form we can read."""
    match = _YEARS.search(line)
    if match is None:
        return None
    asked = match.group(1)
    return int(asked) if asked.isdigit() else _WORD_NUMBERS[asked.lower()]


def _year_of(text: str) -> int | None:
    match = re.search(r"\b(19|20)\d{2}\b", str(text))
    return int(match.group()) if match else None


def years_held(profile: Profile, *, today: date | None = None) -> float | None:
    """Years of dated experience in the profile, overlaps counted once.

    None when no role carries a readable date - an unreadable date is not a
    short career, the same rule the rest of this tool follows.
    """
    now = today or datetime.now(UTC).date()
    spans: list[tuple[int, int]] = []
    for role in profile.experience:
        start = _year_of(role.start)
        if start is None:
            continue
        if norm(str(role.end)) in _PRESENT or not str(role.end).strip():
            end = now.year
        else:
            end = _year_of(role.end) or now.year
        spans.append((start, max(end, start)))

    if not spans:
        return None

    # Union the spans so two overlapping roles are not counted twice.
    total = 0
    covered: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if covered and start <= covered[-1][1]:
            covered[-1] = (covered[-1][0], max(covered[-1][1], end))
        else:
            covered.append((start, end))
    for start, end in covered:
        total += end - start
    return float(total)


def extract(job: Job, vocabulary: frozenset[str] = frozenset()) -> list[Requirement]:
    """Every line the posting asks for, with the terms worth looking up.

    Falls back to `keywords` when a posting states no requirements at all -
    plenty are one prose paragraph, and "0 of 0" reads as a score of zero.
    `keywords` is what the posting screens for, which is the right material.
    """
    stated = [(line, "required") for line in job.requirements]
    stated += [(line, "nice_to_have") for line in job.nice_to_have]

    if not stated and job.keywords:
        stated = [(word, "required") for word in job.keywords]

    found = []
    for line, kind in stated:
        terms = salient_terms(line, vocabulary)
        found.append(Requirement(
            text=line.strip(), kind=kind, terms=terms,
            why=("" if terms else
                 "No concrete term to look for - judge this one yourself."),
        ))
    return found


def basis_of(job: Job) -> str:
    return "requirements" if (job.requirements or job.nice_to_have) else "keywords"
