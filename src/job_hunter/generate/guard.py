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

#: A word, keeping the punctuation that belongs inside technical names: C++, .NET,
#: CI/CD. `[^\W\d_]` is "a Unicode letter", so an accented word survives whole -
#: matching on `A-Za-z` cut "expérience" into "exp" and "rience" and then showed
#: the user the fragment.
_LETTERISH = r"(?:[^\W_]|[+#])"
_WORD = re.compile(rf"[^\W\d_]{_LETTERISH}*(?:[./-]{_LETTERISH}+)*")

#: A figure worth checking: 35%, 1,200, 3+, 4.5, 60k, and the French "25 000".
_FIGURE = re.compile(r"\d{1,3}(?:[   ]\d{3})+|\d[\d,.]*\s?%?\+?[kKmM]?")
#: Sentence boundaries, so the capitalised first word of a sentence is not read
#: as a proper noun. "Led migration to Kubernetes" should only ever flag Kubernetes.
_SENTENCE = re.compile(r"(?<=[.!?;:])\s+|\n+|^", re.MULTILINE)

#: Languages whose capitalisation this can actually read. The proper-noun check
#: assumes a capitalised word mid-sentence is a name; German capitalises every
#: noun, so there it reports the entire letter. Rather than bury a correct
#: document under findings, it says plainly that it could not check the wording.
CHECKED_LANGUAGES = frozenset({"en", "fr"})

#: Capitalised mid-sentence words that are not claims about the candidate.
_HARMLESS = frozenset("""
i a an the and or but of for to in on at by with from as into over under
i'm i've my me we our their his her its this that these those
january february march april may june july august september october november december
monday tuesday wednesday thursday friday saturday sunday
je tu il elle on nous vous ils elles mon ma mes notre nos votre vos leur leurs
le la les un une des du au aux et ou mais donc car dans sur avec pour par chez
ce cet cette ces celui ceux qui que dont ainsi
janvier février mars avril mai juin juillet août septembre octobre novembre décembre
lundi mardi mercredi jeudi vendredi samedi dimanche
""".split())


def _norm(word: str) -> str:
    """Fold a word to its comparison form: lowercase, no possessive, no plural 's'."""
    word = word.lower().strip(".,;:!?()[]{}\"'’«»").removesuffix("'s")
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _digits(figure: str) -> str:
    """Fold a figure to the digits of the number it denotes.

    Locale-aware, because the same quantity is written `25,000` in English and
    `25 000` or `25.000` in French, and a CV written in one language is regularly
    quoted in a letter written in the other. Comparing the raw characters flagged
    the candidate's own metric as unverified.
    """
    text = re.sub(r"[   ]", "", figure)
    digits = re.sub(r"[^\d.,]", "", text)
    if "." in digits and "," in digits:
        # Whichever comes last is the decimal point; the other grouped thousands.
        thousands = "," if digits.rfind(".") > digits.rfind(",") else "."
        digits = digits.replace(thousands, "").replace(",", ".")
    elif sep := ("." if "." in digits else "," if "," in digits else ""):
        # One separator, three digits behind it: it grouped thousands, not tenths.
        head, _, tail = digits.rpartition(sep)
        digits = (head + tail) if (len(tail) == 3 and head) else digits.replace(sep, ".")
    return digits.rstrip(".")


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

    @classmethod
    def wording_of(cls, *sources: object) -> Support:
        """Support for the words in `sources`, but not for their figures.

        Naming a thing is not claiming it: an answer has to write "Workday" to
        say it has never used Workday, and that honest no is the answer this
        package exists to allow. A figure is an assertion wherever it appears,
        so those are deliberately left unsupported.
        """
        return cls(terms=cls.of(*sources).terms)

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


#: Function words that make a passage English. Used to tell an English document
#: apart from the posting it was written for - the tailorer writes a CV summary
#: in English under a French posting, and that summary is checkable.
_ENGLISH = frozenset("""
the and of to in with for on at by from as is are was were be been has have had
i my we our that this these those it its not but or into over under across
""".split())


def _looks_english(text: str) -> bool:
    words = [_norm(m.group()) for m in _WORD.finditer(text)]
    if len(words) < 8:  # too short to tell, and too short to be worth guessing
        return False
    return sum(word in _ENGLISH for word in words) / len(words) >= 0.10


def reads(text: str, language: str = "") -> bool:
    """Whether the proper-noun check can read this passage's capitalisation.

    Two signals, because neither alone is right. The posting's language is what
    the letter and the answers are written in, by instruction - but not the CV
    summary, which comes back in English however the posting was written. So an
    unreadable posting language switches the check off only for text that does
    not itself look English.

    An unnamed language reads as yes: a posting whose language the parser could
    not name is usually English, and a review aid that quietly switches itself
    off is worse than one that occasionally over-reports.
    """
    if not language or language.strip().lower()[:2] in CHECKED_LANGUAGES:
        return True
    return _looks_english(text)


def check(text: str, support: Support, *, path: str,
          asked: Support | None = None, language: str = "") -> list[Issue]:
    """Every claim in `text` that the support does not back.

    `asked` is the vocabulary of a question being answered. Those words are
    still unsupported - saying "yes, I have used X" must be flagged - but the
    finding says so differently, because "remove it" is the wrong advice for a
    word the answer cannot avoid writing.

    `language` is the document's own language. Figures are checked whatever it
    is; the wording check needs `CHECKED_LANGUAGES` to mean anything.
    """
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

    if not reads(text, language):
        issues.append(Issue(
            path=path, severity=Severity.WARNING,
            message=f"This is written in {language!r}, and the wording check only "
                    "reads English and French - the figures above were checked, the "
                    "words were not. Read it against your profile yourself.",
        ))
        return issues

    for term in sorted(_unsupported_terms(text, support)):
        if asked is not None and asked.backs_term(term):
            message = (f"{term!r} is the question's own term and is not in your profile - "
                       "check the answer does not claim it.")
        else:
            message = (f"{term!r} does not appear in your profile. Remove it, or add it "
                       "to your profile if it is true.")
        issues.append(Issue(path=path, severity=Severity.WARNING, message=message))
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


def check_all(fields: dict[str, object], support: Support,
              *, language: str = "") -> list[Issue]:
    """Run `check` over a mapping of path -> string or list of strings.

    An unreadable language would otherwise repeat its one finding once per
    paragraph, so it is said once for the whole document.
    """
    issues: list[Issue] = []
    for path, value in fields.items():
        if isinstance(value, str):
            issues.extend(check(value, support, path=path, language=language))
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                if isinstance(item, str):
                    issues.extend(check(item, support, path=f"{path}[{i}]",
                                        language=language))
    if not reads("\n".join(_strings(v) for v in fields.values()), language):
        said = next((i for i in issues if "wording check" in i.message), None)
        issues = [i for i in issues if "wording check" not in i.message]
        if said is not None:
            issues.append(said.model_copy(update={"path": next(iter(fields), "text")}))
    return issues
