---
name: jobhunt-tailor
description: >
  Rewrite a CV for one specific job using only facts already in the profile -
  choosing which roles and bullets to show and how to word them. Use when
  someone wants their CV tailored to a posting.
allowed-tools: Bash, Read, Write
---

# Tailor the CV

You never write an employer, a job title, a date, a degree or a certification.
You answer with **indices into the profile** and reworded bullet text, and
everything else is copied across. A fabricated employer is not something caught
afterwards - it cannot be expressed.

## 0. Coach first, when there is time

```bash
python3 tailor.py --coach --run <run>
```

Per bullet: whether it carries a figure, whether it opens with a duty
("Responsible for"), whether it runs long - and for each missing figure, the
question whose answer is the fix ("How long did a release take before this,
and after?"). Read the questions to the person. Their answers go into
`profile.yaml`, not into the CV: the profile is the source, and a number that
only exists in a CV is a number nobody can trace. Then tailor.

Never fill a figure in yourself. An unanswered question stays a bullet without
a figure, which is honest; a guessed number is not.

## 1. Read the brief

```bash
python3 tailor.py --brief --run <run>
```

Prints the profile with every role and project numbered, then the posting.
Everything you may choose from is in there. Nothing else is.

## 2. Write the selection

```json
{
  "summary": "Two sentences, in their voice, aimed at this job.",
  "roles": [
    {"index": 0, "bullets": ["Reworded bullet.", "Another."]},
    {"index": 2, "bullets": ["..."]}
  ],
  "projects": [1],
  "skills": ["dbt", "Python", "Airflow"]
}
```

```bash
python3 tailor.py selection.json --run <run>
```

## Rewording

The bullets the person wrote are usually duty statements: "Responsible for the
on-call rotation", "Develop production backend systems using Python, NestJS,
FastAPI, PostgreSQL, React and Next.js." A reader gives each one two seconds.
Rewording within the facts is your job here; it is what most of the quality
of the page comes from.

| Do | Not |
|---|---|
| Lead with the outcome the bullet already states: "Cut ETL runtime 35% by rewriting the dbt models" | Add an outcome it does not state |
| Start with the verb: "Ran the on-call rotation" | "Responsible for the on-call rotation" |
| Cut filler: "using various technologies", "in a fast-paced environment" | Cut a fact |
| Group the tools: "in Python and TypeScript (FastAPI, NestJS, React)" | Add a tool the profile does not list |
| Keep a bullet to two lines and a role to three to five bullets | Keep every bullet because it is true |
| Write a two-sentence summary that names the role and the two strongest facts | Write a paragraph |

The test of a rewording: could the person read the new bullet and the old one
and say "yes, that is the same thing I did"? If it took a number, a tool, an
employer, a title or a date the profile does not hold to get there, it is not
a rewording. The tool reports every figure it cannot find in the profile, and
every bullet that still opens with a duty; read both before you export.

## The rules

- **Select and reorder; do not invent.** A reworded bullet must say the same
  thing as the original. Sharpening "Improved performance" into "Cut p99
  latency 40%" invents a number.
- **Every figure must already be in the profile.** If the profile says 35%, the
  bullet says 35%.
- **Drop roles freely.** That is what tailoring is. The tool reports which ones
  you left off so the candidate can disagree.
- **Order is not yours.** Roles come out in the profile's order whatever order
  you list them in - a past role above the current one reads as a mistake on a
  CV, whatever the reasoning.
- **Skills must exist in the profile.** Anything you add is dropped and
  reported. Reorder them so what this job cares about comes first.
- **The summary may name the company and the role.** Nothing else new.
- **Lead with what the posting asks for**, where the profile backs it. That is
  the entire mechanism by which `shown` improves, and it is legitimate: you are
  surfacing evidence, not creating it.

## Exit 2

The document has a blocking problem. Fix the JSON and run it once more. Do not
export it.
