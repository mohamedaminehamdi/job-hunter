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

## 1. Read the brief

```bash
python3 tailor.py --brief --run <run> x
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

## The rules

- **Select and reorder; do not invent.** A reworded bullet must say the same
  thing as the original. Sharpening "Improved performance" into "Cut p99
  latency 40%" invents a number - and the guard will catch it, which is worse
  than not writing it.
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

The document has a blocking problem - usually placeholder text. Fix the JSON
and run it once more. Do not export it.

## Afterwards

Guard findings print on stderr. Each one is a sentence to read again. They are
warnings, not errors: the check is lexical, so it occasionally flags something
legitimate. Relay them; do not silently rewrite around them.
