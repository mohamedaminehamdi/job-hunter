"""How a document looks.

Two axes only, because more would be a design tool rather than a job tool: an
accent colour and a type family. The company-branded cover letter is this same
neutral theme with the colour read off the job page - not a different template.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEX = re.compile(r"^#[0-9a-f]{6}$", re.IGNORECASE)

#: Ink, not black: pure black on white prints harsher than it looks on screen.
NEUTRAL_ACCENT = "#1f2933"

SANS = ('-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Helvetica, Arial, '
        "sans-serif")
SERIF = 'Charter, Georgia, "Iowan Old Style", "Times New Roman", serif'


@dataclass(frozen=True)
class Theme:
    name: str = "neutral"
    accent: str = NEUTRAL_ACCENT
    body_font: str = SANS
    heading_font: str = SANS

    @property
    def is_branded(self) -> bool:
        return self.accent.lower() != NEUTRAL_ACCENT

    @property
    def ink(self) -> str:
        """Body text colour. Always readable, never the accent."""
        return "#14181d"

    @property
    def muted(self) -> str:
        return "#5b6570"

    @property
    def rule(self) -> str:
        return "#dfe3e8"


NEUTRAL = Theme()
#: A serif CV reads as more traditional; some fields expect it.
CLASSIC = Theme(name="classic", body_font=SERIF, heading_font=SERIF)

THEMES: dict[str, Theme] = {"neutral": NEUTRAL, "classic": CLASSIC}


def branded(colour: str, *, base: Theme = NEUTRAL) -> Theme:
    """`base` in the company's colour, or `base` unchanged if there isn't one.

    The colour reaches a stylesheet, so anything that is not a plain hex value
    is refused rather than escaped.
    """
    colour = (colour or "").strip().lower()
    if not _HEX.match(colour):
        return base
    return Theme(name="company", accent=colour,
                 body_font=base.body_font, heading_font=base.heading_font)


def resolve(name: str | None) -> Theme:
    """Look up a theme by name, falling back to neutral."""
    return THEMES.get((name or "").strip().lower(), NEUTRAL)
