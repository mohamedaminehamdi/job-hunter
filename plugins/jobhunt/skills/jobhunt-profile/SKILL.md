---
name: jobhunt-profile
description: >
  Turn a CV into profile.yaml, the single source of truth every other jobhunt
  skill reads, and report what is missing from it. Use when someone wants their
  CV read into a structured profile, or asks what is wrong with their profile.
allowed-tools: Bash, Read, Write, Glob
---

# Build the profile

`profile.yaml` is the source of truth. Every other jobhunt skill reads it and
nothing may claim anything it does not contain. It is worth getting right once.

The script is next to this file - `${CLAUDE_PLUGIN_ROOT}/skills/jobhunt-profile/profile.py`
under a plugin install. No API key, no install, any Python 3.9+.

## Check what is there

```bash
python3 profile.py
```

Prints the profile's state as JSON and its problems on stderr. Exit 1 means
there is no profile, or something blocking is missing.

## Build one from a CV

1. Find the CV. `ls jobhunt/cv/` - if there is more than one, ask which.
2. Get the words out:

   ```bash
   python3 profile.py --cv jobhunt/cv/their-cv.pdf
   ```

   A `.docx`, `.md` or `.txt` is read for you. A **PDF is handed back** - open
   it with Read and work from what you see. You can read a PDF; the script
   cannot, and a bad PDF text extractor silently mangles a career.

3. Write `jobhunt/profile.yaml` from what you read. The shape:

   ```yaml
   personal:
     name: Ada
     surname: Lovelace
     headline: Data Engineer          # the one line under the name
     email: ada@example.com
     phone: "+49 170 0000000"         # quote it, or YAML reads it as a number
     city: Munich
     country: Germany
     github: https://github.com/ada   # full URLs, with the scheme
     linkedin: https://linkedin.com/in/ada
     website: ""
   summary: One or two sentences in their own voice.
   skills: [Python, dbt, Airflow]
   experience:
     - position: Data Engineer
       company: Acme
       start: "2021"                  # quote every date
       end: Present
       location: Munich, Germany
       industry: Logistics
       bullets:
         - Cut ETL runtime 35% by rewriting the dbt models.
       skills: [dbt, Airflow]
   education:
     - level: MSc
       institution: TU Munich
       field_of_study: Computer Science
       start: "2017"
       end: "2019"
       grade: "1.3"
       courses: [Distributed Systems]
   projects:
     - name: pipe
       description: A tiny scheduler.
       link: https://github.com/ada/pipe
       tech: [Python]
   certifications:
     - {name: dbt Analytics Engineer, issuer: dbt Labs, year: "2023"}
   languages:
     - {name: English, level: fluent}
   ```

4. Normalise and check:

   ```bash
   python3 profile.py --normalise
   ```

## The rules

- **Copy, do not improve.** Their bullets in their words. This is the material
  every later step draws on, and a bullet you invented here becomes a lie on a
  CV three steps later.
- **Bullets carry the weight.** They are the only thing the tailorer can use -
  it selects, reorders and rewords them, and cannot write new ones. A role with
  no bullets contributes nothing.
- **Skills are what fit is measured against.** List what the CV lists.
- **Quote every date and grade.** `end: 2026` reads back as an integer;
  `end: "2026"` is a date.
- **Leave it out rather than guess.** An empty field is honest. A guessed one
  is a claim they did not make.

## Then stop

When you have built a profile from a CV for the first time, **show them the
report and stop**. A model just read their career. They check it before
anything is built on it. Say that plainly.
