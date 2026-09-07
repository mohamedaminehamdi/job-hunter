"""One exception family for everything that generates text.

Callers - the CLI, the web layer - want to catch "generation went wrong" once
and show the message, so each generator's error subclasses this rather than
inventing an unrelated type.
"""

from __future__ import annotations


class GenerationError(RuntimeError):
    """A generator could not produce a usable document. Message is for the user."""
