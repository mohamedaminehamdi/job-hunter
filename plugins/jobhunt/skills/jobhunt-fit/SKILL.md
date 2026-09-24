---
name: jobhunt-fit
description: >
  Score a CV against a job posting and say what is evidenced, what is only
  buried, and what is a real gap - before tailoring and after, so the
  difference is measurable. Use when someone asks how well they match a role.
allowed-tools: Bash, Read
---

# Score the fit

Two numbers, because they answer different questions and only one can move.

**Evidenced** — of what the posting asks for, how much can the *profile* back?
A fact about the candidate. It is **identical before and after tailoring**, by
construction: evidence is looked up in the profile, and rewriting a document
cannot add to it.

**Shown** — of what the profile can back, how much does the *document* put in
front of a reader in the first screenful? This is the one tailoring moves, and
moving it is the whole job: the evidence was already there, buried at bullet
nine.

So a CV that pastes the posting's requirements into its summary scores **zero**
extra and is told off for it - that appears as `parroting`.

```bash
python3 fit.py --run <run> --when before     # before tailoring
python3 fit.py --run <run> --when after      # after, needs cv.yaml
```

Run `before` **before** you tailor. There is no way to reconstruct it after.

## Reading the output

- **`not checkable`** — requirements like "strong communication skills".
  Nothing concrete to look for, so they leave the denominator rather than being
  counted as failures. The candidate judges those.
- **`gaps`** — asked for, backed by nothing in the profile. Two honest
  responses: close it, or stop applying for jobs that need it. Claiming it
  anyway is not one this tool will help with.
- **`parroting`** — the document names it and the profile cannot back it. A
  tripwire. Non-zero means the writing is repeating the posting.
- **`regressions`** — the profile backs it and the document dropped it. Usually
  a tailoring mistake worth undoing.
- **`basis: keywords`** — the posting stated no requirements, so it fell back
  to keywords. Coarser, and it says so.

## What to say about it

Say the number and then say what it means. If `evidenced` is 2 of 9, the
honest sentence is "your profile backs two of the nine things they ask for" -
not "there is room to improve the match". Do not soften a real gap; the person
is about to spend an hour on an application.

Do not offer to raise the score by adding skills to the profile. The profile
describes what they have done.
