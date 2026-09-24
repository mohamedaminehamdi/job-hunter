"""What the site says, kept next to the code that proves it.

Everything describing a skill is read from that skill's own SKILL.md, so the
page cannot advertise one that does not exist. What lives here is the copy that
is genuinely editorial - and it is short on purpose. This is a page for someone
looking for a job, not a README.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))
import jobhunt as jh  # noqa: E402

HERE = Path(__file__).resolve().parent
SKILLS_DIR = ROOT / "plugins" / "jobhunt" / "skills"
REPO = "mohamedaminehamdi/job-hunter"

ICONS = json.loads((HERE / "icons.json").read_text(encoding="utf-8"))
BRANDS = json.loads((HERE / "brands.json").read_text(encoding="utf-8"))

# --- the hero ---------------------------------------------------------------

HEADLINE = ["Stop rewriting your CV", "for every single job."]
SUB = ("Keep everything you have ever done in one place. Paste a job link and "
       "get a CV built for it, the recruiters worth messaging, and the message "
       "to send them — in about a minute.")

#: Boards it is regularly pointed at. It takes any job URL - these are the ones
#: worth naming because they are the ones people paste.
BOARDS = ["linkedin", "indeed", "greenhouse", "glassdoor", "upwork"]

# --- the two CVs ------------------------------------------------------------
#
# The centrepiece. Same person, same facts, same profile - the difference is
# which of them a reader meets first. That is the whole argument for tailoring
# and it is the one thing a screenshot can actually show.

JOB = "Senior Data Engineer · Zeta"

#: Both cards are the same six lines out of the same profile, in a different
#: order, and each shows the four a reader gets through before deciding. That
#: is the argument the page makes, so the example has to be literally true -
#: a test fails if the two lists stop being permutations of each other.
POOL = [
    ("Cut ETL runtime 35% by rewriting the dbt models", True),
    ("Own the ingestion pipelines and the on-call rota", True),
    ("Built the finance dashboards used by 40 people", True),
    ("Responsible for various engineering tasks", False),
    ("Worked on internal tooling and reporting", False),
    ("Involved in several cross-team projects", False),
]

#: What a reader gets through before they decide.
SCREENFUL = 4

GENERIC = {
    "label": "The one CV you send everywhere",
    "summary": "Experienced software professional with a strong background in "
               "technology, seeking a challenging new role.",
    "order": [3, 4, 5, 0, 1, 2],
    "note": "Your three strongest lines are below the fold. Most readers never "
            "reach them.",
}

TAILORED = {
    "label": "Built for this posting",
    "summary": "Data engineer who cut ETL runtime 35% by rewriting a dbt "
               "warehouse, and owns the ingestion pipelines behind it.",
    "order": [0, 1, 2, 3, 4, 5],
    "note": "The same six lines. The three this job asks about now come first.",
}


def cv_lines(cv):
    """The lines a reader sees, and how many of them answer the posting."""
    lines = [POOL[i] for i in cv["order"]][:SCREENFUL]
    hits = sum(1 for _, hit in lines if hit)
    return lines, hits, sum(1 for _, hit in POOL if hit)


COMPARE_NOTE = ("Nothing was written for you. Both cards hold the same six "
                "lines from your own profile — only the order and the summary "
                "changed.")

# --- what it takes off your plate -------------------------------------------

REASONS = [
    {"icon": "folder-simple",
     "title": "Everything you have done, in one place",
     "body": "One profile holds every role, project and side thing across every "
             "field you have worked in. You write it once. Each application "
             "draws from it."},
    {"icon": "cursor-click",
     "title": "A CV per job, without the evening",
     "body": "It picks which of your work answers this posting and leads with "
             "it. The rewriting that used to cost you an hour a job costs you "
             "a paste."},
    {"icon": "paper-plane-tilt",
     "title": "The message, already written",
     "body": "It works out who at the company is worth contacting and drafts "
             "something specific enough to get a reply. You press send."},
]

# --- outreach ----------------------------------------------------------------

OUTREACH_TARGETS = [
    {"tier": "Same university", "title": "Alumni at Zeta",
     "why": "By far the best odds — a cold message is ignored, a shared "
            "university is answered."},
    {"tier": "Would be your colleague", "title": "Data Engineer",
     "why": "They reply. People two rungs up do not."},
    {"tier": "Probably the hiring manager", "title": "Head of Data",
     "why": "Worth one message, after the other two."},
]

OUTREACH_MESSAGE = ("I rewrote the dbt models at Acme and cut ETL runtime 35%, "
                    "so the ingestion work in your Senior Data Engineer posting "
                    "caught my eye. How does Zeta split ownership of the "
                    "warehouse day to day?")

OUTREACH_NOTE = ("It never logs in and never sends. It works out who is worth "
                 "writing to, builds the search that finds them, and drafts "
                 "the message — you run it and press send.")

#: It will not write you a career you do not have. No longer the headline,
#: but still the reason the tailoring can be trusted at all.
FLAG = {"claim": "Led the OpenStack migration, cutting costs 73%.",
        "finding": "Neither '73%' nor 'OpenStack' is anywhere in your profile."}

# --- how it works ------------------------------------------------------------

STEPS = [
    {"icon": "file-text", "title": "Drop your CV in, once",
     "body": "It becomes one profile you check and approve. Every application "
             "after that is built from it, so you never retype your history."},
    {"icon": "link-simple", "title": "Paste a job link",
     "body": "Opened in your own browser, so you get the real description and "
             "not a loading spinner. Any board, any URL."},
    {"icon": "cursor-click", "title": "Get the CV and the letter",
     "body": "Built for that posting out of your own work, as PDF and markdown, "
             "in a folder for that job."},
    {"icon": "paper-plane-tilt", "title": "Get who to message, and what to say",
     "body": "The people worth contacting, the searches that find them, and a "
             "draft specific enough to answer."},
]

# --- coming soon --------------------------------------------------------------

SOON = [
    {"icon": "cursor-click", "title": "One-click apply",
     "body": "Fill and submit the form for you, on the boards that allow it."},
    {"icon": "magnifying-glass", "title": "Jobs found for you",
     "body": "Watch the boards for postings your profile already answers."},
    {"icon": "briefcase", "title": "Application tracking",
     "body": "What you sent, when, and what came back — in one list."},
]

SOON_NOTE = ("Not built yet. Today it prepares the application and hands it to "
             "you; the sending is still yours.")

# --- the skills ---# --- the skills -------------------------------------------------------------

ORDER = [
    "jobhunt", "jobhunt-profile", "jobhunt-posting", "jobhunt-fit",
    "jobhunt-tailor", "jobhunt-letter", "jobhunt-pdf", "jobhunt-guard",
    "jobhunt-answer", "jobhunt-outreach", "jobhunt-critique",
]

#: Short enough to scan. The frontmatter description is written for an agent
#: choosing a skill, which is a different job from a person reading a grid.
CARDS = {
    "jobhunt":          ("briefcase", "The whole application",
                         "One job link in, everything below out."),
    "jobhunt-profile":  ("file-text", "Your CV, read once",
                         "Becomes the one file everything else draws on."),
    "jobhunt-posting":  ("link-simple", "The posting, read properly",
                         "In your own browser, so nothing is missed."),
    "jobhunt-fit":      ("gauge", "How well you match",
                         "Two numbers. Only one of them moves."),
    "jobhunt-tailor":   ("cursor-click", "A CV for this job",
                         "Your bullets, chosen and reordered."),
    "jobhunt-letter":   ("paper-plane-tilt", "A letter worth reading",
                         "Short, specific, in the posting's language."),
    "jobhunt-pdf":      ("download-simple", "The file you attach",
                         "PDF and markdown, from the browser you have."),
    "jobhunt-guard":    ("shield-check", "Check any writing",
                         "Point it at a bio, a letter, anything."),
    "jobhunt-answer":   ("warning-circle", "The form questions",
                         "Including how to write an honest no."),
    "jobhunt-outreach": ("magnifying-glass", "Who to message",
                         "The searches to run, and what to say."),
    "jobhunt-critique": ("terminal-window", "What's still weak",
                         "Read before you send, not after."),
}


def read_skills():
    """Every skill, from its own SKILL.md, so the page cannot invent one."""
    listed = {p.name for p in SKILLS_DIR.iterdir() if p.is_dir()}
    missing = sorted(listed - set(ORDER))
    if missing:
        raise SystemExit(f"tools/site/data.py does not list: {missing}")

    found = []
    for name in ORDER:
        skill = SKILLS_DIR / name
        meta = jh.yaml_load((skill / "SKILL.md").read_text(encoding="utf-8")
                            .split("---\n", 2)[1])
        icon, headline, plain = CARDS[name]
        found.append({"name": name, "icon": icon, "headline": headline,
                      "plain": plain,
                      "description": " ".join(meta["description"].split())})
    return found


# --- where it installs ------------------------------------------------------
#
# The split that matters: some agents read a skills directory in your home,
# some only read the project you have open.

AGENTS = [
    {"id": "claude", "name": "Claude Code", "scope": "global",
     "path": "~/.claude/skills/", "plugin": True,
     "note": "Installs once, works in every project."},
    {"id": "codex", "name": "OpenAI Codex", "scope": "global",
     "path": "~/.codex/skills/", "plugin": True,
     "note": "Installs once, works in every project."},
    {"id": "gemini", "name": "Gemini CLI", "scope": "global",
     "path": "~/.gemini/skills/", "plugin": False,
     "note": "Installs once, works in every project."},
    {"id": "cursor", "name": "Cursor", "scope": "project",
     "path": ".cursor/skills/", "plugin": False,
     "note": "Cursor reads skills from the folder you have open, not from your "
             "home directory. Keep one folder for your job search and run it "
             "there."},
    {"id": "cline", "name": "Cline", "scope": "project",
     "path": ".cline/skills/", "plugin": False,
     "note": "Cline reads skills from the folder you have open, so run this "
             "where you want to work."},
    {"id": "windsurf", "name": "Windsurf", "scope": "project",
     "path": ".windsurf/skills/", "plugin": False,
     "note": "Windsurf reads skills from the folder you have open, so run this "
             "where you want to work."},
    {"id": "other", "name": "Something else", "scope": "manual",
     "path": "", "plugin": False,
     "note": "Any agent that reads a folder of skills will work — these are "
             "plain markdown and plain Python. Download them and put them "
             "wherever yours looks."},
]
