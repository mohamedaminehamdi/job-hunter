"""Making sense of what a model actually returns.

Every generator asks for JSON and every provider occasionally answers with
fenced JSON, JSON wrapped in a sentence of apology, or JSON cut off halfway.
That handling lives here so each generator does not reinvent it, and so a fix
for one caller fixes all of them.
"""

from __future__ import annotations

import json
import re

#: Opening or closing code fence on its own line, with or without a language tag.
_FENCE = re.compile(r"^\s*```(?:json)?|```\s*$", re.MULTILINE)


class ParseError(ValueError):
    """The response could not be read as the requested shape."""


def parse_json(raw: str, *, hint: str = "") -> dict:
    """Pull a JSON object out of a model response.

    Forgiving by design: instructing a model to return only JSON reduces the
    noise but never eliminates it. `hint` is appended to the error messages a
    caller wants to end with its own advice ("paste it as YAML instead").
    """
    cleaned = _FENCE.sub("", raw.strip()).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = _salvage(cleaned, hint)

    if not isinstance(parsed, dict):
        raise ParseError(f"Expected a JSON object, not a {type(parsed).__name__}.")
    return parsed


def _salvage(cleaned: str, hint: str) -> object:
    """Second attempt: take the outermost braces and ignore the prose around them."""
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1:
        raise ParseError(_join("The model did not return JSON.", hint)) from None
    if end <= start:
        # Opened an object and never closed it - almost always a hit max_tokens.
        raise ParseError(
            _join("The model returned malformed JSON (the response looks cut off).", hint)
        ) from None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ParseError(f"The model returned malformed JSON: {exc}") from exc


def _join(message: str, hint: str) -> str:
    return f"{message} {hint}".strip()
