"""The outreach page a person reads, with the links already built."""

from __future__ import annotations

from .models import NOTE_CHARS, TIERS, Outreach

_WHY_TIER = {
    "alumni": "Same school, now there. The best odds by a distance - a cold "
              "message is ignored, a shared university is answered.",
    "peer": "Would be your colleague. They reply; people two rungs up do not.",
    "manager": "Likely the hiring manager.",
    "recruiter": "Gatekeeping rather than advising, but worth a message.",
}


def page(plan: Outreach) -> str:
    out = [f"# Outreach — {plan.role} at {plan.company}", "",
           "Nobody is contacted for you. These are searches to run and a message",
           "to adapt; the sending is yours.", ""]

    for tier in TIERS:
        targets = [t for t in plan.targets if t.tier == tier]
        if not targets:
            continue
        out += [f"## {tier.title()}", "", _WHY_TIER.get(tier, ""), ""]
        for target in targets:
            out.append(f"- **{target.title}**" + (f" — {target.why}" if target.why else ""))
            if target.search_url:
                out.append(f"  <{target.search_url}>")
        out.append("")

    message = plan.message
    out += ["## What to say", ""]
    if message.subject:
        out += [f"**Subject** ({len(message.subject)} chars)", "", message.subject, ""]
    if message.note:
        out += [f"**Connection note** ({len(message.note)} of {NOTE_CHARS} characters "
                "— LinkedIn rejects anything longer)", "", message.note, ""]
    if message.inmail:
        out += [f"**Message** ({len(message.inmail.split())} words)", "",
                message.inmail, ""]

    if plan.issues:
        out += ["## Check before you send", ""]
        out += [f"- {issue}" for issue in plan.issues]
        out.append("")

    out += ["---", "",
            "Ask a question you actually want answered. A student asking a future",
            "colleague what the on-call rota is really like gets a reply; asking a",
            "stranger for a referral does not."]
    return "\n".join(out).rstrip() + "\n"
