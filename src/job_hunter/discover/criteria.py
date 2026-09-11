"""What you are looking for, and where to look for it.

Saved as `~/.job-hunter/search.yaml` next to the profile, and edited the same
way: plain YAML, in the web UI or in your editor. Like `Profile`, loading never
raises - a half-written criteria file should come back as a checklist of what is
missing, not a traceback on startup.

The source lists are here rather than in `Settings` because they are search
input, not configuration: which Greenhouse boards to poll is the same kind of
decision as which job titles to look for.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ..config import load_settings
from ..profile.models import Issue, Severity

FILENAME = "search.yaml"

#: Enough to be a search. Below this every board returns its whole catalogue.
MIN_TITLES = 1


class Criteria(BaseModel):
    """The search, as the user describes it."""

    #: Role titles to look for. The first is treated as the primary one by the
    #: sources that only accept a single query string.
    titles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)

    remote: bool = True
    hybrid: bool = True
    onsite: bool = True

    #: 0 means any age. Sources that report no date are never filtered out by
    #: this - an unknown date is not an old one.
    posted_within_days: int = 0
    #: Hits below this never enter the queue. Tune it after your first search.
    min_score: int = 35
    #: Per source, so one noisy board cannot drown the others.
    limit_per_source: int = 30

    company_blacklist: list[str] = Field(default_factory=list)
    title_blacklist: list[str] = Field(default_factory=list)
    location_blacklist: list[str] = Field(default_factory=list)

    #: Board slugs, as they appear in the board's own URL:
    #: boards.greenhouse.io/<slug>, jobs.lever.co/<slug>, jobs.ashbyhq.com/<slug>.
    greenhouse: list[str] = Field(default_factory=list)
    lever: list[str] = Field(default_factory=list)
    ashby: list[str] = Field(default_factory=list)
    #: Any other page that lists jobs - a company's careers page, a board's
    #: search results, a newsletter's archive. Read with a browser like any
    #: other page, so whatever renders in Chrome can be searched.
    pages: list[str] = Field(default_factory=list)

    #: Off by default: their terms prohibit automated access, and the risk is
    #: to your own account. `indeed` additionally serves an anti-bot challenge
    #: to a headless browser nearly every time - it is implemented, it reports
    #: the block clearly, and it will mostly return nothing.
    linkedin: bool = False
    indeed: bool = False

    def report(self) -> list[Issue]:
        """Every problem worth showing, worst first. Never raises."""
        issues: list[Issue] = []
        if len(self.titles) < MIN_TITLES:
            issues.append(Issue(path="titles", severity=Severity.BLOCKING,
                                message="Add at least one job title to search for."))
        if not self.sources_enabled:
            issues.append(Issue(
                path="sources", severity=Severity.BLOCKING,
                message="No source to search. Add a board slug under greenhouse, "
                        "lever or ashby, a URL under pages, or turn on linkedin.",
            ))
        if not self.locations and not self.remote:
            issues.append(Issue(path="locations", severity=Severity.WARNING,
                                message="No location and remote is off - most "
                                        "sources will return very little."))
        if self.min_score > 80:
            issues.append(Issue(path="min_score", severity=Severity.WARNING,
                                message=f"A minimum score of {self.min_score} will "
                                        "reject almost everything."))
        order = {Severity.BLOCKING: 0, Severity.WARNING: 1, Severity.INFO: 2}
        return sorted(issues, key=lambda i: order[i.severity])

    @property
    def sources_enabled(self) -> list[str]:
        """The adapters this criteria actually gives work to."""
        enabled = [name for name, values in (("greenhouse", self.greenhouse),
                                             ("lever", self.lever),
                                             ("ashby", self.ashby),
                                             ("page", self.pages)) if values]
        if self.linkedin:
            enabled.append("linkedin")
        if self.indeed:
            enabled.append("indeed")
        return enabled

    @property
    def is_searchable(self) -> bool:
        return not any(i.severity is Severity.BLOCKING for i in self.report())

    @property
    def query(self) -> str:
        """The single search string for sources that accept only one."""
        return self.titles[0] if self.titles else ""

    @property
    def where(self) -> str:
        return self.locations[0] if self.locations else ""

    def wants_workplace(self, workplace: str) -> bool:
        """False only when the listing states a workplace the user ruled out."""
        text = workplace.lower()
        if not text:
            return True
        if "remote" in text:
            return self.remote
        if "hybrid" in text:
            return self.hybrid
        if "site" in text or "office" in text:
            return self.onsite
        return True


def criteria_path(home: Path | None = None) -> Path:
    return (home or load_settings().home) / FILENAME


def from_dict(raw: dict) -> Criteria:
    """Build criteria from loose YAML, dropping unknown keys and bad values."""
    known = {k: v for k, v in raw.items() if k in Criteria.model_fields}
    try:
        return Criteria.model_validate(known)
    except Exception:
        # Salvage field by field: one bad line should not lose the whole search.
        criteria = Criteria()
        for key, value in known.items():
            try:
                validated = Criteria.model_validate({key: value})
                criteria = criteria.model_copy(update={key: getattr(validated, key)})
            except Exception:
                continue
        return criteria


def load(home: Path | None = None) -> Criteria:
    """The saved criteria, or empty ones. Malformed YAML reads as empty."""
    target = criteria_path(home)
    if not target.exists():
        return Criteria()
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return Criteria()
    return from_dict(raw) if isinstance(raw, dict) else Criteria()


def save(criteria: Criteria, home: Path | None = None) -> Path:
    target = criteria_path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(criteria.model_dump(mode="json"), sort_keys=False,
                       allow_unicode=True, width=100),
        encoding="utf-8",
    )
    return target


def example() -> str:
    """A filled-in criteria file, for the empty state to show."""
    return yaml.safe_dump(Criteria(
        titles=["Backend Engineer", "Platform Engineer"],
        locations=["Zurich", "Remote"],
        posted_within_days=30,
        greenhouse=["anthropic", "stripe"],
        lever=["ledgerkit"],
        pages=["https://example.com/careers"],
    ).model_dump(mode="json"), sort_keys=False, allow_unicode=True, width=100)
