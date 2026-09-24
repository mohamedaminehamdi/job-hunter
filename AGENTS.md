# job-hunter: instructions for any coding agent

> For **OpenAI Codex**, **GitHub Copilot**, **Cursor**, **Cline**, **Aider**,
> **Gemini CLI**, **Windsurf**, and any other harness that reads project-root
> agent instructions.
>
> **Claude Code users:** you already have this as the `/prep-apply` skill. See
> [CLAUDE.md](CLAUDE.md).

## What this repo is

A toolkit for preparing **one job application**: read the posting, score how
well the user's CV answers it, tailor the CV, write a cover letter, score it
again so the difference is visible, critique both, and draft LinkedIn outreach.

It **applies to nothing and submits nothing.** It produces documents; the person
sends them.

## Why this is portable

The half of this that must be exact is a plain command-line program — argv in,
one line of JSON out, a meaningful exit code. It has no model in it and no
vendor in it:

```
python -m job_hunter.skill <verb> [options]
```

Your contribution is judgement, written to four JSON files. Everything else —
validating the posting, copying the user's employers and dates across, checking
for invented claims, scoring the fit, building URLs, rendering the PDF — is that
program's job, and it behaves identically whichever agent drives it.

So porting to a new harness is not a rewrite. It is this file.

## Setup, once

```bash
pip install -e .
playwright install chromium          # it drives a real browser to read job pages
git config core.hooksPath .githooks  # stops the user ever committing their own CV
```

The user puts their CV in `cv/`. There is **no API key** — you are the model.

## How the user will ask

Claude Code has a slash command. You almost certainly do not, so expect the
request in plain language with a URL in it:

> "prepare an application for https://boards.greenhouse.io/acme/jobs/42"

If there is no URL, ask for one, or offer to take the job description pasted as
text — that path is fully supported and common.

## The procedure

**Read [`.claude/skills/prep-apply/SKILL.md`](.claude/skills/prep-apply/SKILL.md)
and follow it.** That file is the authoritative version, and the reference files
it names under `.claude/skills/prep-apply/references/` carry the rules for each
step. Two things there are Claude-specific and you should ignore them: the YAML
frontmatter, and `$url` — substitute the URL the user gave you.

They live under `.claude/` because that is the only place Claude Code looks, and
a symlink to a tidier location breaks on Windows checkouts. Nothing in them is
Claude-specific beyond those two lines.

In brief, so you know the shape before you read it:

| # | Command | You supply |
|---|---|---|
| 0 | `doctor` | — |
| 1 | `fetch <url>` | — |
| 2 | `job --run <run>` | `job.json`, from `page.txt` |
| 3 | `fit --run <run> --when before` | — |
| 4 | `cv --run <run>` | `cv-selection.json` |
| 5 | `letter --run <run>` | `letter-draft.json` |
| 6 | `fit --run <run> --when after` | — |
| 7 | — | `critique.md` |
| 8 | `outreach --run <run>` | `outreach.json` |
| 9 | `report --run <run>` | — |

Every command prints the run directory it settled on. Use what it prints; never
construct the path.

## Exit codes

| Code | Meaning | What you do |
|---|---|---|
| 0 | fine | carry on |
| 1 | the **user** must fix something | stop, relay the message as written, do not work around it |
| 2 | the draft is not fit to send | fix the JSON, run once more, then stop |
| 3 | the JSON could not be read | write it again, once |

## Things you must not do

- **Never apply to anything.** No form, no submit button, no email.
- **Never scrape LinkedIn.** It walls automated access and the risk lands on the
  user's account. `skill outreach` builds searches for them to run.
- **Never invent.** Every claim traces to the user's profile. If the profile
  does not show it, it does not go in.
- **Never write `cv.md` or `letter.md` yourself.** They are rendered from
  `cv.yaml` by `skill cv`. If the PDF step fails, report that and move on —
  writing the document yourself hands the employers, titles and dates back to a
  model, and that is the one thing this repo exists to prevent.
- **Do not fetch job pages with your own browser tool.** Boards render
  descriptions client-side; `skill fetch` drives a real browser and gets the
  text. If it fails, use the paste path.

## Tool names

The procedure mentions Claude Code's tool names. Yours are equivalent:

| Claude Code | Codex | Copilot | Cursor | Cline | Aider |
|---|---|---|---|---|---|
| `Bash` | `shell` | terminal | terminal | `execute_command` | `/run` |
| `Read` | `read_file` | read | read | `read_file` | `/add` |
| `Write` | `write_file` | create | write | `write_to_file` | `/add` then edit |
| `Glob` | `glob` | search | search | `search_files` | inline |

Only `Bash` is load-bearing — everything the toolkit does is behind
`python -m job_hunter.skill`. Reading and writing files is how you hand it the
four JSON files.

## Per-harness notes

| Harness | How it picks this up |
|---|---|
| **OpenAI Codex** | Reads `AGENTS.md` from the project root automatically. |
| **GitHub Copilot** | Reads `.github/copilot-instructions.md`, which points here. |
| **Cursor** | Reads `AGENTS.md`. Older versions: copy this to `.cursorrules`. |
| **Cline** | Reads `AGENTS.md` as system context at session start. |
| **Aider** | Reads `AGENTS.md` if present, otherwise `README.md`. |
| **Gemini CLI** | Reads `AGENTS.md`; `GEMINI.md` also works if you prefer. |
| **Windsurf** | Reads `AGENTS.md`; older versions use `.windsurfrules`. |
| **Claude Code** | `.claude/skills/prep-apply/` — `/prep-apply <url>`. |

If your harness is not listed and reads none of these, point it at this file by
hand. There is nothing else to install.

## Checking it still works here

```bash
pytest                            # 200+ tests, no model needed
ruff check job_hunter tests
```

The pipeline is fully testable offline because your whole contribution is four
JSON files — `tests/test_skill_io.py` supplies them from a fixture and runs the
entire flow with no agent involved.
