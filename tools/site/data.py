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

HEADLINE = ["Apply for jobs without", "claiming things you", "haven't done."]
SUB = ("Drop in a job link. Your coding agent reads the posting, rebuilds your "
       "CV from your own history, and flags anything it can't back.")

#: Boards it is regularly pointed at. It takes any job URL - these are the ones
#: worth naming because they are the ones people paste.
BOARDS = ["linkedin", "indeed", "greenhouse", "glassdoor", "upwork"]

# --- the three things -------------------------------------------------------

REASONS = [
    {"icon": "shield-check",
     "title": "It can't invent an employer",
     "body": "Your agent points at your profile — it never writes a company, a "
             "title or a date. There is nowhere for a made-up job to go."},
    {"icon": "gauge",
     "title": "The score can't be gamed",
     "body": "Evidence is only ever looked for in your CV. Paste the job ad into "
             "your summary and you score exactly zero extra."},
    {"icon": "key",
     "title": "No key. No account.",
     "body": "Your agent is the model, so what you already pay for covers it. "
             "Nothing is uploaded and nothing is sent."},
]

# --- how it works -----------------------------------------------------------

STEPS = [
    {"icon": "file-text", "title": "Your CV, read once",
     "body": "It becomes one file you check and approve. Everything after is "
             "built only from what's in it."},
    {"icon": "link-simple", "title": "Paste a job link",
     "body": "Opened in your own browser, so you get the real description and "
             "not a loading spinner."},
    {"icon": "gauge", "title": "See where you stand",
     "body": "Before anything is written — including the gaps. If a job needs "
             "something you haven't done, it says so."},
    {"icon": "paper-plane-tilt", "title": "Get the files",
     "body": "A tailored CV and a cover letter, as PDF, in a folder for that "
             "job. You send them. It never applies for you."},
]

#: Real output, from a real run. The numbers on the page are these.
FIT = {"evidenced": 4, "of": 9, "before": 2, "after": 4, "backed": 4}

#: The one line that shows what the whole thing is for.
FLAG = {"claim": "Led the OpenStack migration, cutting costs 73%.",
        "findings": ["The figure '73%' is not in your profile.",
                     "'OpenStack' does not appear in your profile."]}

# --- the skills -------------------------------------------------------------

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
