"""What a fit report is made of.

The shapes here encode the one idea that makes measuring fit twice honest:
**evidence lives in the profile, never in the document.** A requirement is
evidenced because the candidate has done the thing, and no amount of rewriting
can change that. What a tailored CV changes is whether the evidence is *shown*.

That split is why `evidenced` is identical before and after, and why copying a
requirement's words into a summary earns nothing but a warning.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

#: How strong a piece of evidence is, strongest first. Where a claim is backed
#: matters to a reader: a sentence describing doing the thing is worth more than
#: the same word sitting in a comma-separated list.
DEMONSTRATED = "demonstrated"   # a bullet on a role - someone did this
CREDENTIALED = "credentialed"   # a certificate, a course, a language - a third party said so
CLAIMED = "claimed"             # a skills list or a project's tech - cheap to write
ASSERTED = "asserted"           # the summary or headline - self-description
STRENGTHS = (DEMONSTRATED, CREDENTIALED, CLAIMED, ASSERTED)

#: What became of one requirement.
EVIDENCED = "evidenced"               # every concrete term in it is backed
PARTLY = "partly_evidenced"           # some are
NOT_EVIDENCED = "not_evidenced"       # none are
NOT_CHECKABLE = "not_checkable"       # nothing concrete to look for
STATUSES = (EVIDENCED, PARTLY, NOT_EVIDENCED, NOT_CHECKABLE)


class Evidence(BaseModel):
    """One place in the profile that backs one term."""

    term: str = ""
    #: Where it was found, as a path: "experience[0].bullets[2]".
    where: str = ""
    kind: str = CLAIMED
    #: The sentence itself, so a reader can judge the evidence rather than trust
    #: a number.
    quote: str = ""


class Requirement(BaseModel):
    """One thing the posting asks for, and what the profile has to say about it."""

    text: str = ""
    #: required or nice_to_have, in the posting's own division.
    kind: str = "required"
    #: The concrete words worth looking for. Empty means not checkable.
    terms: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    status: str = NOT_CHECKABLE
    evidence: list[Evidence] = Field(default_factory=list)
    #: Would a reader see this in the first screenful of the document?
    shown_in_skim: bool = False
    #: Is it anywhere in the document at all?
    present_anywhere: bool = False
    #: Set when nothing concrete could be looked for, saying so plainly.
    why: str = ""

    @property
    def is_checkable(self) -> bool:
        return self.status != NOT_CHECKABLE

    @property
    def is_backed(self) -> bool:
        return self.status == EVIDENCED


class FitReport(BaseModel):
    """One measurement of one CV against one job."""

    when: str = "before"
    job_label: str = ""
    job_url: str = ""
    #: "requirements" normally; "keywords" when the posting states none and we
    #: fell back, so the reader knows the measurement is coarser.
    basis: str = "requirements"
    skim_bullets: int = 0
    requirements: list[Requirement] = Field(default_factory=list)
    #: Terms the document mentions that the profile cannot back. The tripwire:
    #: non-zero means the writing is parroting the posting.
    parroting: list[str] = Field(default_factory=list)
    #: Evidence the profile has that this document leaves out entirely.
    regressions: list[str] = Field(default_factory=list)
    #: Stated in the posting, not evidenced anywhere, with the line that asked.
    gaps: list[str] = Field(default_factory=list)
    #: Years asked for against years the profile can date, when both are legible.
    years_note: str = ""

    @property
    def required(self) -> list[Requirement]:
        return [r for r in self.requirements if r.kind == "required"]

    @property
    def checkable(self) -> list[Requirement]:
        return [r for r in self.required if r.is_checkable]

    def count(self, status: str) -> int:
        return sum(1 for r in self.required if r.status == status)

    @property
    def evidenced(self) -> int:
        return self.count(EVIDENCED)

    @property
    def shown(self) -> int:
        """Backed requirements a reader would actually meet in the first screenful."""
        return sum(1 for r in self.checkable if r.is_backed and r.shown_in_skim)

    @property
    def present(self) -> int:
        return sum(1 for r in self.checkable if r.is_backed and r.present_anywhere)

    @property
    def nice_to_have(self) -> list[Requirement]:
        return [r for r in self.requirements if r.kind == "nice_to_have"]
