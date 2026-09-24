"""Who to message about this job, and what to say to them.

No scraping, no automation, nobody contacted for you: LinkedIn walls automated
access and the risk lands on the sender's account. What is automatable is the
part worth automating - which roles are worth a message, a search that finds
them, and a message specific enough to answer.
"""

from __future__ import annotations

from . import links, render
from .models import INMAIL_WORDS, NOTE_CHARS, SUBJECT_CHARS, TIERS, Message, Outreach, Target

__all__ = ["INMAIL_WORDS", "NOTE_CHARS", "SUBJECT_CHARS", "TIERS", "Message",
           "Outreach", "Target", "links", "render"]
