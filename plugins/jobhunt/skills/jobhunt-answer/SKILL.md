---
name: jobhunt-answer
description: >
  Draft and check an answer to an application form question so it stays inside
  what the profile can back, including an honest no. Use for "Do you have
  experience with X?", "Why do you want to work here?" and similar form fields.
allowed-tools: Bash, Read
---

# Answer an application question

The questions that get lied to. This is built so an honest no is a real answer.

```bash
python3 answer.py "Your draft" --question "Do you have experience with Workday?"
python3 answer.py --file draft.txt --question "..." --run <run> --limit 1000
```

`--run` lets the answer name the company and role. `--limit` is the form's
character cap, if it states one - forms cut answers off rather than refuse
them, and knowing before you paste is better than after.

## Writing the answer

**If they have done it:** say what they did, with the figure from the profile.
One sentence of evidence beats a paragraph of adjectives.

**If they have not:** say so, then say the nearest true thing.

> No - I have not used Workday. I have run the equivalent integration work on
> SAP SuccessFactors, including the payroll export, and would expect the shape
> to be familiar.

That is a better answer than a hedge, and it is the one this tool exists to
make easy. The guard will flag "Workday" as the question's own term - that
finding is *expected* on an honest no and is not a reason to remove the word.
The answer cannot be written without it.

**Never**: "I have some familiarity with", "I have been exposed to", "I am a
fast learner and would pick it up quickly". Those read as a no that hopes
nobody notices, and an interviewer reads them that way too.

**For "why do you want to work here"**: one specific thing about what the
company does, and one thing from their own history that connects. No mission
paragraph.

## Exit 2

Over the form's limit. Cut it and try again.
