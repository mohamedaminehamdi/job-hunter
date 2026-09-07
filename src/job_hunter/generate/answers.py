"""Answering the free-text questions on an application form.

"Why do you want to work here?", "Describe a time you...", "Do you have
experience with X?". The last one is why the honesty rule matters most here: the
truthful answer is sometimes no, and a model asked to be helpful will not give it.

Answers are short, plain, and checked against the profile like everything else.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..config import Settings
from ..jobs.models import Job
from ..profile.models import Issue, Profile, Severity, placeholder_issues
from . import guard, llm, parsing
from .errors import GenerationError
from .facts import profile_block

DEFAULT_WORDS = 150

_SYSTEM = """You draft an answer to one question on a job application form.

Rules:
- Only facts from the candidate's profile. Never invent experience, tools or figures.
- If the profile does not support a yes, do not write a yes. Say plainly what the
  candidate has done that is closest, or that they have not done it. An honest
  no is a correct answer.
- Answer the question asked, in the first person, in the candidate's own register.
- No filler, no restating the question, no flattery.
- Stay within the word limit given.
- Write in the language of the question.
- Return only JSON matching the requested shape. No prose, no code fences."""

_SHAPE = """{
  "answer": "",
  "unsupported": ""
}"""

_NOTES = """Field notes:
- answer: the text the candidate would paste into the form.
- unsupported: if the question asks about something the profile does not show,
  say so here in one sentence, addressed to the candidate. Empty otherwise."""


class AnswerError(GenerationError):
    """The answer could not be produced."""


class Answer(BaseModel):
    question: str = ""
    text: str = ""
    #: The model's own note on what the profile could not back. Shown to the user.
    caveat: str = ""
    job_label: str = ""
    job_slug: str = ""
    issues: list[Issue] = Field(default_factory=list)

    @property
    def all_issues(self) -> list[Issue]:
        order = {Severity.BLOCKING: 0, Severity.WARNING: 1, Severity.INFO: 2}
        found = [*self.issues, *placeholder_issues(self.text, "answer")]
        if self.caveat:
            found.append(Issue(path="answer", severity=Severity.WARNING,
                               message=f"The model flagged a gap: {self.caveat}"))
        if not self.text:
            found.append(Issue(path="answer", severity=Severity.BLOCKING,
                               message="The model returned an empty answer."))
        return sorted(found, key=lambda i: order[i.severity])

    @property
    def word_count(self) -> int:
        return len(self.text.split())


def answer(profile: Profile, job: Job, question: str, *, words: int = DEFAULT_WORDS,
           settings: Settings | None = None) -> Answer:
    """Draft an answer to one application question."""
    if not question.strip():
        raise AnswerError("No question given.")

    prompt = (
        f"Answer this application question in at most {words} words.\n\n"
        f"Question: {question.strip()}\n\n"
        f"Return exactly this JSON shape:\n\n{_SHAPE}\n\n{_NOTES}\n\n"
        f"=== PROFILE (the only facts you may use) ===\n{profile_block(profile)}\n\n"
        f"=== JOB ===\n{job.brief()}"
    )
    try:
        response = llm.complete(prompt, system=_SYSTEM, settings=settings)
        data = parsing.parse_json(response.text, hint="Try again.")
    except parsing.ParseError as exc:
        raise AnswerError(str(exc)) from exc

    text = data.get("answer") if isinstance(data.get("answer"), str) else ""
    caveat = data.get("unsupported") if isinstance(data.get("unsupported"), str) else ""
    support = guard.Support.of(profile) | guard.Support.of(
        job.company, job.title, job.location
    )

    return Answer(
        question=question.strip(),
        text=(text or "").strip(),
        caveat=(caveat or "").strip(),
        job_label=job.label,
        job_slug=job.slug,
        issues=guard.check((text or "").strip(), support, path="answer"),
    )
