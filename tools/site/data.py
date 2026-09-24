"""What the site says, kept next to the code that proves it.

Everything on the page that describes a skill is read from that skill's own
SKILL.md, so the site cannot advertise a skill that does not exist or describe
one that has changed. What lives here is the copy that is genuinely editorial -
the headline, the reasons, the install routes.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))
import jobhunt as jh  # noqa: E402

SKILLS_DIR = ROOT / "plugins" / "jobhunt" / "skills"
REPO = "mohamedaminehamdi/job-hunter"

#: The order the skills are shown in: the flow, not the alphabet.
ORDER = [
    "jobhunt", "jobhunt-profile", "jobhunt-posting", "jobhunt-fit",
    "jobhunt-tailor", "jobhunt-letter", "jobhunt-pdf", "jobhunt-guard",
    "jobhunt-answer", "jobhunt-outreach", "jobhunt-critique",
]

#: A short label for the card - the frontmatter description is written for an
#: agent choosing a skill, which is a different job from a person scanning a
#: page. Both are shown; this is the one in large type.
HEADLINES = {
    "jobhunt": "The whole application",
    "jobhunt-profile": "Your CV, read once",
    "jobhunt-posting": "The posting, read properly",
    "jobhunt-fit": "How well you actually match",
    "jobhunt-tailor": "A CV for this job",
    "jobhunt-letter": "A letter worth reading",
    "jobhunt-pdf": "The file you attach",
    "jobhunt-guard": "Does this claim anything you can't back?",
    "jobhunt-answer": "The form questions",
    "jobhunt-outreach": "Who to message",
    "jobhunt-critique": "What's still weak",
}

#: Shown on the card in the reader's words rather than the agent's.
PLAIN = {
    "jobhunt": "Give it a job link. It does everything below, in order, and "
               "tells you what is still weak before you send anything.",
    "jobhunt-profile": "Reads your CV into one YAML file that everything else "
                       "draws on. You check it once; nothing is invented after.",
    "jobhunt-posting": "Loads the job page in your own browser, so you get the "
                       "description and not a loading spinner.",
    "jobhunt-fit": "Two numbers: what your profile can back, and how much of "
                   "that a reader sees in the first screenful. Only the second "
                   "one moves when you tailor.",
    "jobhunt-tailor": "Picks which roles and bullets to show and how to word "
                      "them — out of what is already in your profile.",
    "jobhunt-letter": "Three or four paragraphs, grounded in things you have "
                      "actually done, in the posting's own language.",
    "jobhunt-pdf": "Renders the CV and the letter. Uses the browser you already "
                   "have. Refuses to export a document with a hole in it.",
    "jobhunt-guard": "Point it at any writing — a bio, a letter, a LinkedIn "
                     "summary. It flags every figure and name your profile "
                     "cannot back.",
    "jobhunt-answer": "\"Do you have experience with X?\" — including how to "
                      "write an honest no that still reads well.",
    "jobhunt-outreach": "Works out who is worth a message, builds the searches, "
                        "drafts something specific enough to answer. You send it.",
    "jobhunt-critique": "Reads the finished application against the posting and "
                        "says what is wrong with it.",
}


def read_skills():
    """Every skill, from its own SKILL.md."""
    found = []
    for name in ORDER:
        skill = SKILLS_DIR / name
        body = (skill / "SKILL.md").read_text(encoding="utf-8")
        meta = jh.yaml_load(body.split("---\n", 2)[1])
        script = next(iter(sorted(skill.glob("*.py"))), None)
        found.append({
            "name": name,
            "short": name.replace("jobhunt-", "") if name != "jobhunt" else "all",
            "headline": HEADLINES[name],
            "plain": PLAIN[name],
            "description": " ".join(meta["description"].split()),
            "script": script.name if script else "",
            "standalone": script is not None,
        })
    missing = sorted({p.name for p in SKILLS_DIR.iterdir() if p.is_dir()} - set(ORDER))
    if missing:
        raise SystemExit(f"tools/site/data.py does not list: {missing}")
    return found


#: Where each agent reads skills from, and therefore which install route it
#: gets. The split that matters: some read a global directory, some only read
#: the project you are in.
AGENTS = [
    {"id": "claude", "name": "Claude Code", "scope": "global",
     "path": "~/.claude/skills/",
     "plugin": True,
     "note": "Installs for every project. The plugin route also gives you "
             "updates with one command."},
    {"id": "codex", "name": "OpenAI Codex", "scope": "global",
     "path": "~/.codex/skills/",
     "plugin": True,
     "note": "Installs for every project."},
    {"id": "gemini", "name": "Gemini CLI", "scope": "global",
     "path": "~/.gemini/skills/",
     "plugin": False,
     "note": "Installs for every project."},
    {"id": "cursor", "name": "Cursor", "scope": "project",
     "path": ".cursor/skills/",
     "plugin": False,
     "note": "Cursor reads skills from the project you have open, not from "
             "your home directory — so this installs into the folder you run "
             "it in. Run it again in each project, or keep one folder for your "
             "job search and work there."},
    {"id": "cline", "name": "Cline", "scope": "project",
     "path": ".cline/skills/",
     "plugin": False,
     "note": "Cline reads skills per project, so this installs into the folder "
             "you run it in."},
    {"id": "windsurf", "name": "Windsurf", "scope": "project",
     "path": ".windsurf/skills/",
     "plugin": False,
     "note": "Windsurf reads skills per project, so this installs into the "
             "folder you run it in."},
    {"id": "other", "name": "Something else", "scope": "manual",
     "path": "",
     "plugin": False,
     "note": "Any agent that reads a folder of skills will work — the skills "
             "are plain markdown and plain Python. Download the folder and put "
             "it wherever your agent looks."},
]

HEADLINE = "Job applications that can't claim things you haven't done."

SUB = ("Eleven skills for the coding agent you already use. They read the "
       "posting, tailor your CV out of your own history, and flag every "
       "sentence your profile can't back — then hand you the files. "
       "They apply to nothing.")

#: Three reasons, each one a thing the tool does differently rather than a
#: feature it has.
REASONS = [
    {"title": "It can't invent an employer",
     "body": "The model never writes a company, a title, a date or a degree. "
             "It answers with <em>indices into your profile</em> and the facts "
             "are copied across. A fabricated employer isn't caught afterwards "
             "— there is nowhere for it to be written."},
    {"title": "The score can't be gamed",
     "body": "Evidence is looked up in your profile, never in the document. So "
             "a CV that pastes the job ad into its summary scores <em>zero</em> "
             "extra and gets told off for it. What tailoring moves is whether "
             "a reader meets your evidence in the first screenful."},
    {"title": "No key, no account, no install",
     "body": "Your agent is the model, so your own subscription pays for it. "
             "The scripts are standard-library Python and run on whatever you "
             "already have. Nothing is uploaded and nothing is sent."},
]

#: Real output, captured from a real run against a live posting. Not mocked.
#: Real output, from a real run. Wrapped narrower than the terminal prints it
#: so it fits the hero column without a scrollbar - the numbers and the wording
#: are the tool's own.
FIT_OUTPUT = """Fit for Senior Data Engineer at Zeta

Evidenced in your profile:    4 of 9
  (unchanged by tailoring - it is what you have done)
  not checkable:              2

Shown in the first screenful: 2 of 4  ->  4 of 4   +2
Present anywhere in the CV:   4 of 4  ->  4 of 4

Not evidenced anywhere in your profile:
  · OpenStack   "Experience running OpenStack in production"
  · German      "German B2 or above\""""

#: What one prepared application leaves behind. Real file names from a real run.
RUN_FILES = [
    ("README.md",    "what is in here, and what to check"),
    ("fit-before.md", "how your CV answered this job as it stood"),
    ("cv.pdf",       "the tailored CV, to attach"),
    ("cv.md",        "the same, to paste into a form"),
    ("letter.pdf",   "the cover letter"),
    ("fit-after.md", "what the tailoring actually bought"),
    ("critique.md",  "what is still weak in both"),
    ("outreach.md",  "who to message, and what to say"),
]

GUARD_OUTPUT = """$ jobhunt-guard "Led the OpenStack migration,
                  cutting costs 73%."

The figure '73%' is not in your profile - check it
before you send this.
'OpenStack' does not appear in your profile. Remove
it, or add it to your profile if it is true."""

ANSWER_OUTPUT = """$ jobhunt-answer --question "Do you have experience
                  with Workday?" "No - I have not used
                  Workday. I have run the equivalent
                  integration work on SAP SuccessFactors,
                  including the payroll export."

'Workday' is the question's own term and is not in
your profile - check this does not claim it."""
