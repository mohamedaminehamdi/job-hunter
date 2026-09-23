---
name: prep-apply
description: >
  Prepare one job application end to end from a job URL - crawl the posting,
  score how well the CV answers it before and after tailoring, write a tailored
  CV and a cover letter as PDF and markdown, critique them, and draft LinkedIn
  outreach. Applies to nothing and submits nothing.
argument-hint: <job-url>
arguments: [url]
allowed-tools: Bash(python -m job_hunter.skill:*), Read, Write, Glob
---

# Prepare one application

The job: `$url`

## What this never does

- **Never applies to anything.** It produces documents; the person sends them.
- **Never scrapes LinkedIn.** It works out who is worth messaging and builds the
  searches. They run the search.
- **Never invents.** Every claim in every document traces to their profile. If
  the profile does not show it, it does not go in - a missing skill is not
  yours to solve.
- **Never writes `cv.md` or `letter.md` yourself.** Those are rendered from
  `cv.yaml` by `skill cv`. If the PDF step fails, say so and move on. Writing
  the document yourself hands the employers, titles and dates back to you, and
  that is the one thing this repo is built to prevent.

You do not use `WebFetch` here. Job boards render their descriptions
client-side, so `WebFetch` gets a loading spinner where `skill fetch` gets the
posting.

## Before anything

```
python -m job_hunter.skill doctor
```

**No profile yet?** This is their first run. Do the intake, once:

1. `ls cv/` - if there is more than one CV, ask which.
2. `python -m job_hunter.skill profile --cv <file>` prints its text.
3. Read `references/cv-intake.md` and write `profile.yaml` from that text.
4. `python -m job_hunter.skill profile --normalise`
5. **Show them the report and stop.** A model just read their CV. They check it
   before anything is built on it. Say that plainly, and tell them to re-run
   `/prep-apply <url>` when they are happy.

**No URL given?** Ask for one, or offer to take the job description pasted as
text - that path is fully supported, see step 1.

## The steps

### 1. Get the posting

```
python -m job_hunter.skill fetch $url
```

Prints `{"run": "...", "title": "...", "text_chars": N}`. Use the `run` it gives
you; do not construct the path.

**If it exits 1** - a login wall, or too little text - that is normal and
common. A large share of job links are LinkedIn URLs that show nothing to a
logged-out browser. Do this:

> Ask the person to paste the job description. Write it to `page.txt` in the run
> directory yourself, write `page.json` with `{"url": "<the url>", "title": ""}`,
> and carry on at step 2.

Never work around a wall any other way. Inventing a description is inventing
the job.

### 2. Read the posting

Read `page.txt`. Read `references/job-extraction.md`. Write `job.json` into the
run directory, then:

```
python -m job_hunter.skill job --run <run>
```

It validates what you wrote, overrides the URL and brand colour with what was
actually observed, and renames the run to `runs/<date>-<company-role>/`. **Use
the `run` path it prints from here on** - it has changed.

Exit 1 means the posting is too thin to tailor against. Offer the paste path.

### 3. Score the fit as it stands

```
python -m job_hunter.skill fit --run <run> --when before
```

**Show the person this output before you write anything.** It answers "is this
worth applying to at all", which is their decision and not yours.

Its `gaps` list is also your brief for the next step: those are the things the
profile cannot back. Do not claim them.

### 4. Tailor the CV

Read `references/cv-tailoring.md`, `profile.yaml`, `job.yaml` and
`fit-before.md`. Write `cv-selection.json`, then:

```
python -m job_hunter.skill cv --run <run>
```

You choose which roles, projects and skills appear and how the bullets read.
Every employer, title, date and degree is copied from the profile by the script.

Exit 2 means something in it is not fit to export - a placeholder, a missing
name. Fix the selection and run it once more. If it fails again, stop and report.

### 5. Write the letter

Read `references/cover-letter.md`. Write `letter-draft.json`, then:

```
python -m job_hunter.skill letter --run <run> --branded
```

Drop `--branded` if the posting had no colour. Write in the language of the
posting - a German posting gets a German letter.

### 6. Score it again

```
python -m job_hunter.skill fit --run <run> --when after
```

This prints the before/after together. `evidenced` will not have moved, and
that is correct: it is what the person has done, and no rewrite changes it.
What should move is `shown`.

If `claimed but not evidenced` is not empty, the CV is repeating the posting.
Go back to step 4 and take those claims out.

### 7. Critique the drafts

Read `references/critique.md`. Write `critique.md` in the run directory - the
only file you write as prose, because there is nothing to validate in it.

### 8. Outreach

Read `references/outreach.md`. Write `outreach.json`, then:

```
python -m job_hunter.skill outreach --run <run>
```

You name the roles worth contacting. The script builds every LinkedIn URL and
checks the message against the profile and against LinkedIn's length limits.

Exit 2 means a message is over a hard cap. Shorten it and run once more.

### 9. Finish

```
python -m job_hunter.skill report --run <run>
```

## What the exit codes mean

| Code | Meaning | What you do |
|---|---|---|
| 0 | fine | carry on |
| 1 | the **person** must fix something | stop, relay the message as written, do not work around it |
| 2 | the draft is not fit to send | fix the JSON, run once more, then stop |
| 3 | the JSON could not be read | write it again, once |

## What you tell them at the end

- the before/after, in the tool's own words
- anything in `gaps` - the things this job asks for that they cannot back
- the run directory, and what is in it
- the LinkedIn searches as clickable links
- that nothing has been sent, and applying is theirs to do
