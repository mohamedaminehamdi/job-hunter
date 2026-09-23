"""Who to write to, and what to say.

Kept small on purpose. The tool's contribution is knowing *which* roles are
worth a message and making the message specific; finding the actual person
takes a human thirty seconds and no terms of service.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

#: Ordered by how likely a reply is, which is not the order people expect.
ALUMNI = "alumni"          # same school, now there - by far the best odds
PEER = "peer"              # would be your colleague; they answer, VPs do not
MANAGER = "manager"        # likely the hiring manager
RECRUITER = "recruiter"    # gatekeeping rather than advising
TIERS = (ALUMNI, PEER, MANAGER, RECRUITER)

#: LinkedIn's hard limit on a connection note. Over it, the message is simply
#: rejected when it is pasted, so it is checked here rather than discovered there.
NOTE_CHARS = 280
INMAIL_WORDS = 150
SUBJECT_CHARS = 70


class Target(BaseModel):
    """One kind of person worth writing to, and the search that finds them."""

    tier: str = PEER
    title: str = ""
    why: str = ""
    search_url: str = ""


class Message(BaseModel):
    subject: str = ""
    #: The short one, for a connection request.
    note: str = ""
    #: The longer one, for an InMail or a first message after connecting.
    inmail: str = ""


class Outreach(BaseModel):
    company: str = ""
    role: str = ""
    targets: list[Target] = Field(default_factory=list)
    message: Message = Field(default_factory=Message)
    issues: list = Field(default_factory=list)
