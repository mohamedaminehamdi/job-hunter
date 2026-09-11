"""Deciding which of fifty search hits are worth your attention.

Deterministic and lexical, for three reasons: a search returns hundreds of
listings and a model call each would cost more than the tailoring that follows;
a score you cannot explain is a score you cannot tune; and the same listing must
score the same today as yesterday or the queue reshuffles under you.

So this counts overlaps and says which ones it counted. It is a filter, not a
judgement - `min_score` decides what reaches the queue, and everything that
reaches it is still yours to read.
"""

from __future__ import annotations

import re

from ..profile.models import Profile
from .criteria import Criteria
from .models import Listing, Match

#: Weights, summing to 100. Title dominates: it is the one field every source
#: fills in, and the one that decides whether a role is the right kind at all.
TITLE_POINTS = 40
SKILL_POINTS = 30
LOCATION_POINTS = 20
FRESHNESS_POINTS = 10

_WORD = re.compile(r"[a-z0-9][a-z0-9+#.]*", re.IGNORECASE)

#: Words that carry no signal in a job title. Seniority words are deliberately
#: absent: "senior" is exactly the kind of mismatch worth scoring down.
_NOISE = frozenset("""
a an the and or of for to in at on with by from new our we you your job role
position opening opportunity career careers hiring m f d w x h
""".split())


#: Words nearly every engineering title contains. Sharing one of these with a
#: title you asked for means nothing - "AI Engineer, GTM" is not a "Backend
#: Engineer" - so a title match needs something distinctive on top.
_GENERIC = frozenset("""
engineer engineering developer development manager management analyst scientist
designer specialist lead architect consultant associate intern director officer
staff senior junior principal
""".split())


def _tokens(text: str) -> set[str]:
    return {m.group().lower() for m in _WORD.finditer(text)} - _NOISE


def _title_score(listing: Listing, profile: Profile,
                 criteria: Criteria) -> tuple[int, list[str]]:
    """How close the listing's title is to something you asked for.

    Measured against the criteria first and the profile's own history second, so
    a title you did not think to list still scores if you have held it.
    """
    found = _tokens(listing.title)
    if not found:
        return 0, []

    def overlap(wanted: str) -> float:
        tokens = _tokens(wanted)
        if not tokens:
            return 0.0
        shared = tokens & found
        # Generic words alone are not a match, however many of them there are.
        return len(shared) / len(tokens) if shared - _GENERIC else 0.0

    best_wanted, best = "", 0.0
    for wanted in criteria.titles:
        if (ratio := overlap(wanted)) > best:
            best_wanted, best = wanted, ratio
    if best >= 0.5:
        how = "matches" if best > 0.99 else "partly matches"
        return round(TITLE_POINTS * best), [f"Title {how} {best_wanted!r}."]

    held = [role.position for role in profile.experience if role.position]
    if profile.personal.headline:
        held.append(profile.personal.headline)
    for wanted in held:
        if (ratio := overlap(wanted)) > best:
            best_wanted, best = wanted, ratio
    if best >= 0.5:
        # Worth less than an asked-for title: it is a guess from your history.
        return round(TITLE_POINTS * best * 0.8), [
            f"Close to your own {best_wanted!r}, though you did not ask for it."
        ]

    return round(TITLE_POINTS * best), []


def _skills(profile: Profile) -> list[str]:
    """Every skill the profile claims, deduplicated, longest first.

    Longest first so 'Google Cloud' is reported rather than 'Google' when both
    would match the same words.
    """
    named = list(profile.skills)
    for role in profile.experience:
        named.extend(role.skills)
    for project in profile.projects:
        named.extend(project.tech)
    seen: dict[str, str] = {}
    for skill in named:
        if (key := skill.strip().lower()) and key not in seen:
            seen[key] = skill.strip()
    return sorted(seen.values(), key=len, reverse=True)


def _skill_score(listing: Listing, profile: Profile) -> tuple[int, list[str]]:
    """Which of your skills this listing actually names."""
    text = listing.text.lower()
    hits = [skill for skill in _skills(profile)
            if re.search(rf"(?<![a-z0-9]){re.escape(skill.lower())}(?![a-z0-9])", text)]
    if not hits:
        return 0, []

    # Three named skills is already a strong signal; more is not three times as
    # strong, so the scale flattens rather than running away.
    points = min(SKILL_POINTS, round(SKILL_POINTS * len(hits) / 3))
    shown = ", ".join(hits[:4])
    more = f" (+{len(hits) - 4} more)" if len(hits) > 4 else ""
    return points, [f"Names your {shown}{more}."]


def _place_matches(wanted: str, where: str) -> bool:
    """Whether a listing's location is the place you asked for.

    Compared part by part rather than as one string, because boards name a
    place more fully than a person does: "Munich, Germany" has to match
    "Munich, Bavaria, Germany", and it does not as a substring. Qualifying a
    city with its country is what the search engines need to resolve it at all,
    so it must not cost points here.

    The reverse still counts too - a job listed for "Germany" satisfies someone
    who asked for "Munich, Germany".
    """
    parts = [part.strip().lower() for part in wanted.split(",") if part.strip()]
    if not parts or not where.strip():
        return False
    return all(part in where for part in parts) or where.strip() in wanted.lower()


def _location_score(listing: Listing, criteria: Criteria) -> tuple[int, list[str]]:
    where = f"{listing.location} {listing.workplace}".lower()
    if criteria.remote and "remote" in where:
        return LOCATION_POINTS, ["Remote."]
    for wanted in criteria.locations:
        if _place_matches(wanted, where):
            return LOCATION_POINTS, [f"In {wanted}."]
    if not criteria.locations:
        return LOCATION_POINTS // 2, []
    if not where.strip():
        return LOCATION_POINTS // 2, ["No location given."]
    return 0, [f"{listing.location or 'Location'} is not one you asked for."]


def _freshness_score(listing: Listing) -> tuple[int, list[str]]:
    age = listing.age_days
    if age is None:
        # An unknown date is not an old one. Most boards simply do not say.
        return FRESHNESS_POINTS // 2, []
    if age <= 7:
        return FRESHNESS_POINTS, ["Posted this week."]
    if age <= 30:
        return FRESHNESS_POINTS // 2, []
    return 0, [f"Posted {age} days ago."]


def _excluded(listing: Listing, criteria: Criteria) -> str:
    """The one reason this listing is out, or empty. Checked before scoring."""
    haystacks = {
        "company": listing.company.lower(),
        "title": listing.title.lower(),
        "location": f"{listing.location} {listing.workplace}".lower(),
    }
    for field, blacklist in (("company", criteria.company_blacklist),
                             ("title", criteria.title_blacklist),
                             ("location", criteria.location_blacklist)):
        for banned in blacklist:
            if banned.strip() and banned.strip().lower() in haystacks[field]:
                return f"{field.capitalize()} is on your blacklist ({banned})."

    if not criteria.wants_workplace(f"{listing.workplace} {listing.location}"):
        return f"You ruled out {listing.workplace or listing.location} roles."

    age = listing.age_days
    if criteria.posted_within_days and age is not None and age > criteria.posted_within_days:
        return f"Posted {age} days ago, past your {criteria.posted_within_days}-day limit."
    return ""


def score(listing: Listing, profile: Profile, criteria: Criteria) -> Match:
    """Rate one listing, and say why it got what it got."""
    if reason := _excluded(listing, criteria):
        return Match(score=0, reasons=[], excluded=reason)

    total = 0
    reasons: list[str] = []
    for points, said in (_title_score(listing, profile, criteria),
                         _skill_score(listing, profile),
                         _location_score(listing, criteria),
                         _freshness_score(listing)):
        total += points
        reasons.extend(said)
    return Match(score=min(total, 100), reasons=reasons)
