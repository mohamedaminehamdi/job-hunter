# jobhunt

Twelve skills for the coding agent you already use. Keep everything you have
ever done in one place; paste a job link and get a CV built for it, the people
worth messaging, and the message to send them.

**[Install →](https://mohamedaminehamdi.github.io/job-hunter/)** · pick your
agent and copy one command.

---

## What it takes off your plate

An application used to cost you an evening: tailoring the CV, working out who
to contact, writing the message. Every time, for every job.

**Your work lives in one profile.** Every role, project and side thing across
every field you have worked in. You write it once, and each application draws
from it — you never retype your history.

**A CV per job, without the evening.** It picks which of your work answers this
posting and leads with it. Same facts, different order:

```
The one CV you send everywhere        Built for this posting
· Responsible for various tasks       ● Cut ETL runtime 35% (dbt models)
· Worked on internal tooling          ● Own the ingestion pipelines
· Involved in cross-team projects     ● Built the dashboards 40 people use
● Cut ETL runtime 35% (dbt models)    · Responsible for various tasks

1 of 3  in the first screenful        3 of 3  in the first screenful
```

Same six lines from your own profile. Your strongest three were below the fold,
and most readers never reach them.

**The message, already written.** It works out who at the company is worth
contacting — alumni first, because that is what actually gets replies — builds
the searches that find them, and drafts something specific enough to answer.
You press send.

## It still won't write you a career you don't have

Every line traces back to your profile, and anything that doesn't is flagged
before you send it. Faster, not looser.

```
Led the OpenStack migration, cutting costs 73%.
  The figure '73%' is not in your profile - check it before you send this.
  'OpenStack' does not appear in your profile.
```

That is also why the tailoring is worth anything: the score counts evidence
found in *your profile*, never in the document, so a CV that pastes the job ad
into its summary scores zero extra and gets told off for it.

## Coming soon

One-click apply on the boards that allow it, jobs found for you, and
application tracking. **Not built yet** — today it prepares the application and
hands it to you; the sending is still yours.

## Install

Pick your agent on **[the install page](https://mohamedaminehamdi.github.io/job-hunter/)**,
or:

```bash
# any agent, macOS or Linux
curl -fsSL https://raw.githubusercontent.com/mohamedaminehamdi/job-hunter/main/install.sh | sh

# Cursor, Cline and Windsurf read skills per project, not per user
curl -fsSL .../install.sh | sh -s -- --to .cursor
```

Inside Claude Code or Codex you can install it as a plugin instead:

```
/plugin marketplace add mohamedaminehamdi/job-hunter
/plugin install jobhunt@jobhunt
```

Or download a folder from the install page and drop it in. No terminal needed.

**What it needs:** Python 3.9 or newer, which macOS and every Linux already
has, and Chrome, Chromium, Edge or Brave for reading job pages and making PDFs.
No API key — your agent is the model, so whatever you already pay for covers
it.

## Using it

Put your CV somewhere, open your agent in a folder you want to work in, and
say what you want:

> prepare an application for https://boards.greenhouse.io/acme/jobs/42

The first run reads your CV, writes `jobhunt/profile.yaml`, and **stops and
asks you to check it**. A model just read your career; you approve it once, and
everything after is built on facts you have agreed to.

Then you get a folder per job:

```
jobhunt/runs/2026-09-24-acme-senior-data-engineer/
├── fit-before.md     how your CV answered this job as it stood
├── cv.pdf  cv.md     the tailored CV
├── letter.pdf .md    the cover letter
├── fit-after.md      what the tailoring actually bought
├── critique.md       what is still weak in both
├── outreach.md       who to message, the searches to run, what to say
└── job.yaml          the posting, as read
```

## The twelve

Each works on its own. Install just the guard to check a letter you wrote
yourself, or just the fit score to decide whether a job is worth an evening.

| | |
|---|---|
| `jobhunt` | the whole thing, in order |
| `jobhunt-profile` | your CV → one YAML file everything else reads |
| `jobhunt-review` | score the CV on its own, with no job description |
| `jobhunt-posting` | a job URL → structured posting, in your own browser |
| `jobhunt-fit` | how well you match, before and after |
| `jobhunt-tailor` | a CV for this job, out of what you have already done |
| `jobhunt-letter` | three or four paragraphs worth reading |
| `jobhunt-pdf` | the files to attach |
| `jobhunt-guard` | does this writing claim anything you can't back? |
| `jobhunt-answer` | form questions, including how to write an honest no |
| `jobhunt-outreach` | who to message, and what to say |
| `jobhunt-critique` | what's still wrong, before you send it |

## What it does not do today

- **Apply to anything.** It produces the documents; you send them. On the
  roadmap for the boards that allow it — not built yet.
- **Scrape LinkedIn.** LinkedIn walls and throttles automated access and the
  risk lands on *your* account. It builds the searches; you run them, and that
  is not changing.
- **Search for jobs.** You bring the link, for now.
- **Track your applications**, beyond one line per run in `runs/log.md`. It is
  markdown; type what happened next into it.

## A word on honesty

This makes it easy to produce a polished CV quickly. It does not make it safe
to send one you haven't read.

Generated text can still contain claims your profile doesn't support. It tries
hard to surface those — unfilled placeholders block export, the fit score names
what you cannot back, the critique says what is weak — but the last check is
yours. Read what you send.

## When it goes wrong

| What you see | What it means |
|---|---|
| `No Chrome, Chromium, Edge or Brave found` | Install any of them, or set `JOBHUNT_BROWSER`. You still get markdown without one |
| `Only 300 characters came back` | The posting is behind a login wall. Paste the description — that path is fully supported |
| `No profile at ...` | Put a CV somewhere and ask for a profile first |
| `is YAML this reader does not do` | Hand-edited `profile.yaml` using a `{a: b}` map. Use block style |
| The fit score says `0 of 0` | The posting stated no requirements, so it fell back to keywords. Coarser, and it says so |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), and [AGENTS.md](AGENTS.md) for how the
repo is laid out. `pytest` — 443 tests, on Python 3.9 and up.

## License

MIT — see [LICENSE](LICENSE).
