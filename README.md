<div align="center">

<img src="docs/assets/logo.svg" width="76" height="76" alt="">

# jobhunt

**Stop sending the same CV for every single job.**

Eleven skills for the coding agent you already use. Paste a job link, and get a
CV built for that posting, the people worth messaging, and the message to send
them, all from your own work.

[![CI](https://github.com/mohamedaminehamdi/job-hunter/actions/workflows/ci.yml/badge.svg)](https://github.com/mohamedaminehamdi/job-hunter/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776ab)](#install)
[![No API key](https://img.shields.io/badge/API%20key-not%20needed-45c795)](#install)
[![License: PolyForm Noncommercial](https://img.shields.io/badge/license-PolyForm%20Noncommercial-6b7280)](#license)

**[Install](#install)** · [How it works](#how-it-works) · [The eleven skills](#the-eleven-skills) · [When it goes wrong](#when-it-goes-wrong) · [Website](https://mohamedaminehamdi.github.io/job-hunter/)

<a href="https://mohamedaminehamdi.github.io/job-hunter/assets/launch.mp4"><img src="docs/assets/launch.jpg" width="860" alt="Play the 22-second jobhunt launch video"></a>

<sub>Works with Claude Code, Codex, Gemini CLI, Cursor, Cline and Windsurf, on macOS and Linux.</sub>

</div>

## What it does

**One profile, every job.** Every role, project and side thing, across every
field you have worked in, lives in one file. You write it once and each
application draws from it, so you never retype your history.

**A CV per job, without the evening.** It reads the posting, checks every
requirement against your own work, and leads with the lines this job asks for.
Same facts, better order:

<p align="center"><img src="docs/assets/reorder.gif" width="720" alt="The same six CV lines, reordered for a Senior Data Engineer posting. The three lines it asks for move above the fold, and the score goes from 1 of 3 to 3 of 3."></p>

Most readers stop after the first screenful. On the one CV you send everywhere,
your strongest three lines were below it.

**Who to message, and what to say.** It works out who at the company is worth
contacting (alumni first, because they are the ones who reply), builds the
searches that find them, and drafts a note specific enough to answer.

**Your facts, your send button.** The CV is built from lines already in your
profile. It never applies, never logs in and never sends anything: you read it,
and you press send.

## Install

Pick your agent on **[the install page](https://mohamedaminehamdi.github.io/job-hunter/)**, or:

**Claude Code or Codex**, as a plugin, at the prompt:

```text
/plugin marketplace add mohamedaminehamdi/job-hunter
/plugin install jobhunt@jobhunt
```

**Any agent**, from a terminal on macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/mohamedaminehamdi/job-hunter/main/install.sh | sh

# Cursor, Cline and Windsurf read skills per project, not per user
curl -fsSL .../install.sh | sh -s -- --to .cursor
```

**No terminal:** download a folder from the install page and drop it in.

**What it needs:** Python 3.9 or newer, which macOS and every Linux already
has, and Chrome, Chromium, Edge or Brave for reading job pages and making PDFs.
No API key: your agent is the model, so whatever you already pay for covers it.

<details>
<summary><b>Optional:</b> LaTeX for the PDFs</summary>

If you have a TeX engine (`tectonic` is a single binary), CVs and letters are
set in LaTeX instead, which is what most people expect a CV to look like, and
it is several times faster. Nothing needs it: with no engine the browser renders
them exactly as before, and the tool tells you which it used.

</details>

## How it works

Put your CV somewhere, open your agent in a folder you want to work in, and
say what you want:

> prepare an application for https://boards.greenhouse.io/acme/jobs/42

The first run reads your CV, writes `jobhunt/profile.yaml`, and **stops and
asks you to check it**. A model just read your career; you approve it once, and
everything after is built on facts you have agreed to.

Then every job gets its own folder:

```text
jobhunt/runs/2026-09-24-acme-senior-data-engineer/
├── fit-before.md     how your CV answered this job as it stood
├── cv.pdf  cv.md     the tailored CV
├── letter.pdf .md    the cover letter
├── fit-after.md      what the tailoring actually bought
├── critique.md       what is still weak in both
├── outreach.md       who to message, the searches to run, what to say
└── job.yaml          the posting, as read
```

## The eleven skills

Each works on its own. Install just the review to score your CV, or just the
fit score to decide whether a job is worth an evening.

| Skill | What it does |
|---|---|
| `jobhunt` | the whole thing, in order |
| `jobhunt-profile` | your CV → one YAML file everything else reads |
| `jobhunt-review` | score the CV on its own, with no job description |
| `jobhunt-posting` | a job URL → structured posting, in your own browser |
| `jobhunt-fit` | how well you match, before and after |
| `jobhunt-tailor` | a CV for this job, out of what you have already done |
| `jobhunt-letter` | three or four paragraphs worth reading |
| `jobhunt-pdf` | the files to attach |
| `jobhunt-answer` | form questions, including how to write an honest no |
| `jobhunt-outreach` | who to message, and what to say |
| `jobhunt-critique` | what's still wrong, before you send it |

## What it does not do (yet)

- **Apply to anything.** It produces the documents; you send them. One-click
  apply, on the boards that allow it, is on the roadmap and not built yet.
- **Scrape LinkedIn.** LinkedIn walls and throttles automated access, and the
  risk lands on *your* account. It builds the searches; you run them. That is
  not changing.
- **Find jobs.** You bring the link, for now.
- **Track your applications**, beyond one line per run in `runs/log.md`. It is
  markdown, so type what happened next into it.

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
repo is laid out. `pytest` runs the suite, on Python 3.9 and up.

If jobhunt saved you an evening, a star helps the next person find it.

## License

[PolyForm Noncommercial 1.0.0](LICENSE), with one addition: anyone may use it
to look for work for themselves, paid work included. It is not for commercial
use — recruiters, agencies, employers, CV or coaching services, and paid
products need a separate license from the author. Every skill carries a copy
of the [LICENSE](LICENSE).

Earlier versions were released under MIT, and copies of those stay MIT.

## Credits

The launch video was made with [/brag](https://github.com/latent-spaces/brag).
Type is [Geist](https://vercel.com/font), and the icons are
[Phosphor](https://phosphoricons.com/).
