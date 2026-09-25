---
name: jobhunt
description: >
  Prepare one job application end to end from a job URL - read the posting,
  score how well the CV answers it before and after tailoring, write a tailored
  CV and a cover letter as PDF and markdown, critique them, and draft LinkedIn
  outreach. Applies to nothing and submits nothing. Use when someone gives you
  a job link or asks for help applying to a role.
argument-hint: <job-url>
allowed-tools: Bash, Read, Write, Glob
---

# Prepare one application

The job: `$1`

This runs the other eleven jobhunt skills in order. Each one also works on its
own; this is the sequence when someone wants the whole thing.

## Where the scripts are

Every step below runs a Python script that sits next to its own SKILL.md.

- Installed as a plugin: `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/<script>.py`
- Installed on its own: the directory you read that skill's SKILL.md from

They need **no arguments beyond what is shown, no API key, and no install**.
Standard library only, on any Python 3.9 or newer. Call them with `python3`.

## What this never does

- **Never applies to anything.** It produces documents; the person sends them.
- **Never scrapes LinkedIn.** It works out who is worth messaging and builds
  the searches. They run the search.
- **Never invents.** Every claim traces to their profile. If the profile does
  not show it, it does not go in - a missing skill is not yours to solve.
- **Never writes `cv.md` or `letter.md` by hand.** Those are rendered from
  `cv.yaml`. Writing the document yourself hands the employers, titles and
  dates back to you, and that is the one thing this is built to prevent.
- **Never works around a login wall.** If the posting comes back thin, ask for
  the description as text. Working around a wall means inventing a job.

Do not use `WebFetch` for the posting. Job boards render their descriptions
client-side, so `WebFetch` gets a loading spinner where `posting.py` gets the
job.

## Exit codes

| | |
|---|---|
| `0` | fine |
| `1` | the **user** must fix something. Stop and relay the message |
| `2` | the draft is not fit to send. Rewrite the JSON and try once more |
| `3` | your JSON could not be read. Write it again, once |

A `1` is never worked around.

## Before anything

```bash
python3 <jobhunt-profile>/profile.py
```

**Exit 1, no profile?** This is their first run. Do the intake once, following
the `jobhunt-profile` skill, then **stop and ask them to check it**. A model
just read their CV; they approve it before anything is built on it.

**No URL given?** Ask for one, or offer to take the description pasted as
text - that path is fully supported. If they have no job in mind at all and
just want to know how their CV is doing, run `jobhunt-review` instead: it
scores the CV on its own and needs no posting.

## The steps

1. **Read the posting** - `jobhunt-posting`. Fetch, then write the posting as
   JSON and parse it. Note the run directory it prints; every later step needs
   it.
2. **Score it as it stands** - `jobhunt-fit --when before`. Do this *before*
   tailoring. The comparison is the point.
3. **Tailor the CV** - `jobhunt-tailor`. Read the brief, choose roles by index,
   reword their bullets.
4. **Score it again** - `jobhunt-fit --when after`.
5. **Write the letter** - `jobhunt-letter`.
6. **Render both** - `jobhunt-pdf` on `cv.yaml` and on `letter.yaml`.
7. **Critique** - `jobhunt-critique`, then file it with `--write`.
8. **Outreach** - `jobhunt-outreach`.

## When you are done

Tell them, in this order:

1. The **fit numbers**, and what moved. If `evidenced` is low, say so plainly -
   that is a real gap and tailoring cannot close it.
2. Any **guard findings** still open. These are the sentences to read again.
3. Where the files are, and that **nothing has been sent**.

Do not congratulate them on a strong application. Tell them what is weak.
