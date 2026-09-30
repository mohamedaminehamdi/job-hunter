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

#: The headline retypes itself between these two. Same complaint, twice, and
#: the second one is the reason the first one is a problem.
#: One sentence, typed once. It used to alternate between two phrases, which
#: meant the headline never held still long enough to be read by somebody who
#: had just arrived.
HEADLINE_FIXED = "Stop "
HEADLINE_TYPED = "sending the same CV for every single job."

#: Boards it is regularly pointed at. It takes any job URL.
BOARDS = ["linkedin", "indeed", "greenhouse", "glassdoor", "upwork"]

#: How many whole copies of that row the track holds. One copy of these five
#: is about 720px, and the strip has to still cover the bar after a whole copy
#: has slid off the left - so (COPIES - 1) x 720 has to beat the widest screen
#: this is likely to be opened on. Six carries it to 3600px.
BOARD_COPIES = 6

COMPARE_TITLE = "One of these gets read to the end."
COMPARE_SUB = ("The same profile, against one posting. All that changes is "
               "which of your own lines a reader meets first.")

# --- the two CVs ------------------------------------------------------------
#
# The centrepiece. Both cards are the same six lines out of the same profile,
# in a different order, and each shows the four a reader gets through before
# deciding. That is the argument the page makes, so the example has to be
# literally true - a test fails if the two lists stop being permutations.

JOB = "Senior Data Engineer · Zeta"

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
    "label": "The one you send everywhere",
    "summary": "Experienced software professional with a strong background in "
               "technology, seeking a challenging new role.",
    "order": [3, 4, 5, 0, 1, 2],
    "note": "Your three strongest lines are below the fold.",
}

TAILORED = {
    "label": "Built for this posting",
    "summary": "Data engineer who cut ETL runtime 35% by rewriting a dbt "
               "warehouse, and owns the ingestion pipelines behind it.",
    "order": [0, 1, 2, 3, 4, 5],
    "note": "The same six lines, in the order this job cares about.",
}


def cv_lines(cv):
    """The lines a reader sees, and how many of them answer the posting."""
    lines = [POOL[i] for i in cv["order"]][:SCREENFUL]
    hits = sum(1 for _, hit in lines if hit)
    return lines, hits, sum(1 for _, hit in POOL if hit)


COMPARE_NOTE = ("Same six lines from your own profile. Only the order and the "
                "summary changed.")

# --- the day it costs you ----------------------------------------------------

DAY_TITLE = "Ten applications is a day of your life."
DAY_SUB = ("Read the posting, rewrite the CV, find who to message, write the "
           "message. Then again. And again.")

#: The clock runs through these while the counter climbs. Real tasks, in the
#: order you actually do them.
DAY_TASKS = [
    "Reading the posting",
    "Rewriting your summary",
    "Reordering your bullets",
    "Hunting for the hiring manager",
    "Writing the message",
]

DAY_BY_HAND = {"label": "By hand", "count": 10, "unit": "applications",
               "time": "8 hours", "note": "One evening, gone."}
DAY_WITH = {"label": "With jobhunt", "count": 10, "unit": "applications",
            "time": "12 minutes", "note": "You read them before sending."}

# --- the network -------------------------------------------------------------

NET_TITLE = "One message beats ten applications."
NET_SUB = "It finds who, and writes the first one."

#: Three people between you and the job. The alumni edge is drawn strongest
#: because that is the one that actually gets answered.
NET_PEOPLE = [
    {"who": "Alumni", "role": "Same university, works there", "best": True},
    {"who": "Peer", "role": "Would be your colleague", "best": False},
    {"who": "Manager", "role": "Probably hiring for it", "best": False},
]

OUTREACH_MESSAGE = ("I rewrote the dbt models at Acme and cut ETL runtime 35%, "
                    "so the ingestion work in your posting caught my eye. How "
                    "does Zeta split ownership of the warehouse?")

OUTREACH_NOTE = "It never logs in and never sends. You press send."

# --- how it works ------------------------------------------------------------

#: The workflow, stage by stage, each named for the skill that does it and
#: each with a small demo that plays when its step lights up. One posting all
#: the way through - the same Zeta role as the CV comparison above - so the
#: page tells one story rather than six unrelated ones.
FLOW_TITLE = "From a job link to a message worth sending."
FLOW_SUB = "Six steps, one skill each. You paste the link; it does the rest."

FLOW = [
    {"kind": "link", "icon": "link-simple", "skill": "jobhunt-posting",
     "title": "Paste a job link",
     "body": "Any board, any URL. It reads the posting in your own browser and "
             "pulls out what the job actually asks for.",
     "url": "jobs.zeta.io/careers/senior-data-engineer",
     "facts": ["Senior Data Engineer", "Zeta", "Berlin"],
     "asks": ["dbt", "Airflow", "SQL", "Ingestion", "Kafka"]},
    {"kind": "score", "icon": "gauge", "skill": "jobhunt-fit",
     "title": "Score your CV against it",
     "body": "Every requirement, checked against your own work. What backs it, "
             "and what is a real gap - before you spend an evening on it.",
     "checks": [("dbt", True), ("Airflow", True), ("SQL", True),
                ("Ingestion", True), ("Kafka", False)]},
    {"kind": "rewrite", "icon": "file-text", "skill": "jobhunt-tailor",
     "title": "Rewrite the CV for this job",
     "body": "Your strongest lines for this posting move to the top, where a "
             "reader actually gets to them. Same facts, better order."},
    {"kind": "people", "icon": "user-circle", "skill": "jobhunt-outreach",
     "title": "Find the people to reach out to",
     "body": "Alumni first, because they answer. Then the likely hiring manager "
             "and the recruiter - with the LinkedIn searches that find them.",
     "people": [("LK", "Lena K.", "Data Engineer at Zeta", "Alumni · TU Berlin", True),
                ("MS", "Marco S.", "Head of Data", "Hiring manager", False),
                ("AR", "Aylin R.", "Talent Partner", "Recruiter", False)],
     "search": 'site:linkedin.com/in "Zeta" "TU Berlin" data'},
    {"kind": "email", "icon": "paper-plane-tilt", "skill": "jobhunt-outreach",
     "title": "Write the message",
     "body": "A note short enough to be read, specific enough to be answered. "
             "It mentions the thing you share, not a template.",
     "to": "Lena K. · Alumni",
     "message": "Hi Lena - fellow TU Berlin grad here. I rewrote a dbt warehouse "
                "and cut ETL runtime 35%, and saw Zeta is hiring a data engineer. "
                "Would you have 10 minutes to tell me what the team is like?"},
    {"kind": "letter", "icon": "folder-simple", "skill": "jobhunt-letter · jobhunt-pdf",
     "title": "Get the cover letter and the PDFs",
     "body": "A letter in the posting's language, and the files to attach - "
             "all in one folder for this job. Nothing is sent without you.",
     "files": ["cv.pdf", "letter.pdf", "outreach.md", "fit.md"]},
]

#: The rest of the kit - the parts that are not one stage of the flow.
ALSO = [
    ("jobhunt", "All six steps, in order, from one sentence"),
    ("jobhunt-profile", "Your CV, read once into one file"),
    ("jobhunt-review", "Score your CV with no job at all"),
    ("jobhunt-find", "A careers board, ranked against your profile"),
    ("jobhunt-answer", "Application form questions"),
    ("jobhunt-critique", "What is still weak, before you send"),
]

#: It will not write you a career you do not have. No longer the headline,
#: but still the reason the tailoring can be trusted at all.
FLAG = {"claim": "Led the OpenStack migration, cutting costs 73%.",
        "finding": "Neither '73%' nor 'OpenStack' is anywhere in your profile."}

# --- coming soon --------------------------------------------------------------

SOON_TITLE = "What's next."

SOON = [
    {"icon": "cursor-click", "title": "One-click apply",
     "body": "Fill and submit the form for you, on the boards that allow it."},
    {"icon": "briefcase", "title": "Application tracking",
     "body": "What you sent, when, and what came back — in one list."},
]

SOON_NOTE = "Not built yet. Today it prepares the application; you send it."

# --- the skills -------------------------------------------------------------

ORDER = [
    "jobhunt", "jobhunt-profile", "jobhunt-review", "jobhunt-find", "jobhunt-posting",
    "jobhunt-fit", "jobhunt-tailor", "jobhunt-letter", "jobhunt-pdf",
    "jobhunt-answer", "jobhunt-outreach", "jobhunt-critique",
]

#: Short enough to scan. The frontmatter description is written for an agent
#: choosing a skill, which is a different job from a person reading a grid.
CARDS = {
    "jobhunt":          ("briefcase", "The whole application",
                         "One job link in, everything below out."),
    "jobhunt-profile":  ("file-text", "Your CV, read once",
                         "Becomes the one file everything else draws on."),
    "jobhunt-review":   ("gauge", "Score your CV on its own",
                         "No job needed. What's evidence, what's filler."),
    "jobhunt-find":     ("magnifying-glass", "Openings worth reading",
                         "A whole careers board, ranked by your skills."),
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
