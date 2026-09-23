"""What an exit code means, and what the skill should do about it.

Quoted in SKILL.md, so the two cannot drift apart without somebody noticing.
The split that matters is 1 against 2: "the tool cannot continue" and "your
draft is not fit to send" need opposite responses, and collapsing them teaches
the model to retry things that will never work.
"""

from __future__ import annotations

#: Fine.
OK = 0

#: A precondition the *user* has to fix: no profile, no CV, a login wall, a
#: posting too thin to work from. Stop and relay the message. Never work around
#: it - working around a login wall means inventing the job description.
BLOCKED = 1

#: A document was produced and is not fit to export: a blocking issue, or a
#: message over a hard length cap. Rewrite the JSON that produced it and try
#: once more.
UNFIT = 2

#: The JSON could not be read at all - fenced, truncated, or not JSON. Write it
#: again, once.
UNREADABLE = 3

MEANING = {
    OK: "fine",
    BLOCKED: "the user must fix something; stop and tell them",
    UNFIT: "the draft is not fit to send; rewrite it once",
    UNREADABLE: "the JSON could not be read; write it again once",
}
