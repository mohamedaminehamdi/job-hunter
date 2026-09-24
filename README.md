# jobhunt

Eleven skills for the coding agent you already use. They read a job posting,
tailor your CV out of your own history, flag every sentence your profile can't
back, and hand you the files.

**They apply to nothing.** You send them.

**[Install →](https://mohamedaminehamdi.github.io/job-hunter/)** · pick your
agent and copy one command.

---

## The idea

Every CV tool will happily write you a better career. This one is built so it
can't.

**The model never writes an employer.** It answers with *indices into your
profile* and the facts are copied across. A fabricated employer isn't caught
afterwards — there is nowhere for it to be written. What's left is free text,
and that gets checked word by word against your profile:

```
The figure '73%' is not in your profile - check it before you send this.
'OpenStack' does not appear in your profile. Remove it, or add it to your
profile if it is true.
```

**The score can't be gamed.** Evidence is looked up in your profile, never in
the document, so a CV that pastes the job ad into its summary scores zero extra
and gets told off for it.

```
Evidenced in your profile:    4 of 9   (unchanged by tailoring - it is what you have done)
  not checkable:              2        (judge these yourself)

Shown in the first screenful: 2 of 4  ->  4 of 4      +2
Present anywhere in the CV:   4 of 4  ->  4 of 4

Not evidenced anywhere in your profile:
  · OpenStack   "Experience running OpenStack in production"
  · German      "German B2 or above"
```

Two numbers, because they answer different questions. **Evidenced** is what
your profile can back — a fact about you, and it does not move when the CV is
rewritten. **Shown** is how much of that a reader meets in the first screenful,
and that is the one tailoring moves: the evidence was already there, buried at
bullet nine.

A **gap** is something the job needs that nothing in your profile backs. Two
honest responses: close it, or stop applying for jobs that need it. Claiming it
anyway is not one this tool will help with.

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

## The eleven

Each works on its own. Install just the guard to check a letter you wrote
yourself, or just the fit score to decide whether a job is worth an evening.

| | |
|---|---|
| `jobhunt` | the whole thing, in order |
| `jobhunt-profile` | your CV → one YAML file everything else reads |
| `jobhunt-posting` | a job URL → structured posting, in your own browser |
| `jobhunt-fit` | how well you match, before and after |
| `jobhunt-tailor` | a CV for this job, out of what you have already done |
| `jobhunt-letter` | three or four paragraphs worth reading |
| `jobhunt-pdf` | the files to attach |
| `jobhunt-guard` | does this writing claim anything you can't back? |
| `jobhunt-answer` | form questions, including how to write an honest no |
| `jobhunt-outreach` | who to message, and what to say |
| `jobhunt-critique` | what's still wrong, before you send it |

## What it deliberately does not do

- **Apply to anything.** Some employers disqualify applications the applicant
  didn't write. That is their call, and honouring it is yours.
- **Scrape LinkedIn.** LinkedIn walls and throttles automated access and the
  risk lands on *your* account. It builds the searches; you run them.
- **Search for jobs.** You bring the link. There are better job boards than
  anything this would be.
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
repo is laid out. `pytest` — 373 tests, on Python 3.9 and up.

## License

MIT — see [LICENSE](LICENSE).
