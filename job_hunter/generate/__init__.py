"""Everything that turns facts into a document.

Nothing here calls a model any more - Claude Code does that, and writes its
choices to a JSON file. What survives is the half that matters: `assemble`
copies every identity field from the profile, so an invented employer cannot be
expressed, and `guard` checks the free text that is left.
"""

from __future__ import annotations

from . import cover_letter, cv, facts, guard, parsing
from .errors import GenerationError
from .parsing import ParseError, parse_json

__all__ = ["GenerationError", "ParseError", "cover_letter", "cv", "facts",
           "guard", "parse_json", "parsing"]
