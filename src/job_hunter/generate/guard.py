"""Checking generated text against the facts that back it.

The structural half of the honesty rule is handled by construction: generators
return indices into the profile, so employers, dates and degrees are copied and
cannot be invented. What a model *can* still slip in is free text - a figure or
a tool name inside an otherwise real bullet - and that is what this catches.

The check is lexical, not semantic. It compares the words and figures in the
output against the words and figures in the profile. It therefore misses a
plausible-sounding rewording, and occasionally flags something legitimate. It is
a review aid: findings are warnings addressed to the person about to send the
document, never a silent rewrite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel

from ..profile.models import Issue, Severity

#: A word, keeping the punctuation that belongs inside technical names: C++, .NET, CI/CD.
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9+#]*(?:[./-][A-Za-z0-9+#]+)*")
#: A figure worth checking: 35%, 1,200, 3+, 4.5, 60k.
_FIGURE = re.compile(r"\d[\d,.]*\s?%?\+?[kKmM]?")
#: Sentence boundaries, so the capitalised first word of a sentence is not read
#: as a proper noun. "Led migration to Kubernetes" should only ever flag Kubernetes.
_SENTENCE = re.compile(r"(?<=[.!?;:])\s+|\n+|^", re.MULTILINE)

#: Capitalised mid-sentence words that are not claims about the candidate.
_HARMLESS = frozenset("""
i a an the and or but of for to in on at by with from as into over under
i'm i've my me we our their his her its this that these those
january february march april may june july august september october november december
monday tuesday wednesday thursday friday saturday sunday
""".split())


def _norm(word: str) -> str:
    """Fold a word to its comparison form: lowercase, no possessive, no plural 's'."""
    word = word.lower().strip(".,;:!?()[]{}\"'").removesuffix("'s")
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _digits(figure: str) -> str:
    """Fold a figure to its comparison form: just the digits and any decimal point."""
    return re.sub(r"[^\d.]", "", figure).rstrip(".")


@dataclass(frozen=True)
class Support:
    """The vocabulary a generated document is allowed to draw on."""

    terms: frozenset[str] = frozenset()
    figures: frozenset[str] = frozenset()

    def __or__(self, other: Support) -> Support:
        return Support(self.terms | other.terms, self.figures | other.figures)

    @classmethod
    def of(cls, *sources: object) -> Support:
        """Build support from models, strings, or any mix of the two."""
        text = "\n".join(_strings(source) for source in sources)
        return cls(
            terms=frozenset(_norm(m.group()) for m in _WORD.finditer(text)),
            figures=frozenset(
                d for m in _FIGURE.finditer(text) if (d := _digits(m.group()))
            ),
        )

    def backs_term(self, word: str) -> bool:
        normalised = _norm(word)
        return not normalised or normalised in self.terms

    def backs_figure(self, figure: str) -> bool:
        digits = _digits(figure)
        return not digits or digits in self.figures


def _strings(source: object) -> str:
    """Every string inside a model, a list, or a string, flattened."""
    if isinstance(source, str):
        return source
    if isinstance(source, BaseModel):
        # Diagnostics are not facts: an Issue's message must not become support.
        if isinstance(source, Issue):
            return ""
        return "\n".join(
            _strings(getattr(source, name)) for name in type(source).model_fields
        )
    if isinstance(source, (list, tuple, set)):
        return "\n".join(_strings(item) for item in source)
    return ""


def check(text: str, support: Support, *, path: str) -> list[Issue]:
    """Every claim in `text` that the support does not back."""
    if not text or not text.strip():
        return []

    issues: list[Issue] = []
    for figure in sorted({m.group().strip() for m in _FIGURE.finditer(text)}):
        if not support.backs_figure(figure):
            issues.append(Issue(
                path=path, severity=Severity.WARNING,
                message=f"The figure {figure!r} is not in your profile - "
                        "check it before you send this.",
            ))

    for term in sorted(_unsupported_terms(text, support)):
        issues.append(Issue(
            path=path, severity=Severity.WARNING,
            message=f"{term!r} does not appear in your profile. Remove it, or add it "
                    "to your profile if it is true.",
        ))
    return issues


def _unsupported_terms(text: str, support: Support) -> set[str]:
    """Proper nouns and acronyms in the text that the profile never mentions.

    Only words that carry a claim are considered: an acronym anywhere, or a
    capitalised word that is not merely starting a sentence.
    """
    found: set[str] = set()
    for sentence in _SENTENCE.split(text):
        if not sentence or not sentence.strip():
            continue
        words = list(_WORD.finditer(sentence))
        for position, match in enumerate(words):
            word = match.group()
            if len(word) < 2 or _norm(word) in _HARMLESS:
                continue
            acronym = word.isupper()
            proper = word[0].isupper() and position > 0
            if (acronym or proper) and not support.backs_term(word):
                found.add(word)
    return found


def check_all(fields: dict[str, object], support: Support) -> list[Issue]:
    """Run `check` over a mapping of path -> string or list of strings."""
    issues: list[Issue] = []
    for path, value in fields.items():
        if isinstance(value, str):
            issues.extend(check(value, support, path=path))
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                if isinstance(item, str):
                    issues.extend(check(item, support, path=f"{path}[{i}]"))
    return issues
