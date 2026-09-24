---
name: jobhunt-letter
description: >
  Write a cover letter for one job, grounded in the profile, with the contact
  block copied rather than generated. Use when someone wants a cover letter for
  a specific posting.
allowed-tools: Bash, Read, Write
---

# Write the cover letter

Harder than the CV, because a letter is where a model most wants to help by
calling someone "deeply experienced in" whatever the posting asked for.

The contact block is copied from the profile. You write four paragraphs at most.

```json
{
  "greeting": "Dear Acme team,",
  "paragraphs": ["...", "...", "..."],
  "closing": "Kind regards,"
}
```

```bash
python3 letter.py draft.json --run <run>
```

Needs `job.yaml` in the run - read it first, and write in the posting's own
language.

## What makes a letter worth sending

- **Three or four paragraphs.** Longer stops being read.
- **Specific, from the profile.** One concrete thing they did, with the figure
  the profile gives. "I cut ETL runtime 35% by rewriting the dbt models" beats
  a paragraph about passion.
- **Answer the posting's actual ask**, not its company boilerplate.
- **Name a gap if there is a real one.** A letter that says "I have not built
  forecasting models in SQL, and would rather say so than have you find out
  later" is stronger than one that hopes nobody checks. The guard flags those
  words as the posting's own and tells you to check you are not *claiming*
  them - that finding is expected on an honest denial, and it is not a reason
  to delete the sentence.
- **No flattery about the mission.** Everyone writes that paragraph.
- **In the posting's language.** An English "Application:" over French prose
  says nobody read this before sending. The date format follows too.

## What is not allowed

The posting's requirements are **not** a source of things to claim. Naming
Kafka because the job asks for Kafka is the exact failure this exists to
prevent. The letter may name the company, the role and the location; anything
else must come from the profile.

## Exit 2

No body text, or placeholder text left in. Fix the JSON and try once more.
