---
name: jobhunt-review
description: >
  Score a CV on its own, with no job description - how much of it is evidence
  rather than duties, whether the strongest lines are where a reader reaches
  them, and which listed skills nothing in the CV demonstrates. Use when
  someone asks how good their CV is, what is wrong with it, or wants it
  reviewed without a specific job in mind.
allowed-tools: Bash, Read
---

# Review a CV, with no job in mind

```bash
python3 review.py                          # the saved profile
python3 review.py --profile path/to.yaml
python3 review.py --json                   # every finding, not just the top few
```

## What this is, and what it isn't

There are two different questions and they need two different measurements.

**"Does this answer *this* posting?"** needs the posting — that's
`jobhunt-fit`, and it reports what your profile can back against what the job
asks for.

**"Is this CV well built at all?"** needs nothing but the CV. That's this. It
scores out of 100 across six named dimensions, and every point traces to a
line you can go and look at.

It is **not** a probability of being hired, and it is not a judgement of the
person. Nothing readable off a document could be either. A CV at 55 belongs to
someone whose work is not on the page yet.

## The six, and why each one is job-independent

| | worth | what it measures |
|---|---|---|
| `evidence` | 30 | bullets carrying a figure. The single biggest predictor of a bullet being believed |
| `openers` | 15 | bullets starting "Responsible for", "Involved in", "Worked on" — a duty, not a result |
| `order` | 15 | whether each role's strongest line is in its first two. Readers stop early, whatever the job |
| `complete` | 15 | the nine things an employer needs to act: name, email, phone, location, headline, summary, a link, skills, dates |
| `shown` | 15 | listed skills that appear nowhere in the work. A skill nobody can see you use is a word in a list |
| `shape` | 10 | roles with no bullets, roles with more than eight, bullets over 34 words |

Nothing here depends on what an employer wants. Anything that does belongs in
the fit score instead.

## Reading it out

Lead with the **weakest dimension**, not the total. The number is a way to see
progress; the findings are the work.

- **`evidence` low** is the usual answer and the most fixable. Ask them, per
  bullet: how many, how much, how fast, how many people, what did it replace?
  The figures are almost always in their head and not on the page.
- **`shown` low** means the skills list is longer than the story. Either the
  skill belongs in a bullet, or it does not belong on the CV.
- **`order` low** means the material is right and buried. Free to fix.
- **`complete` low** is a five-minute fix and worth naming first because of
  that.

Say which single change would move the number most, and say what it is worth.
Do not rewrite their CV in the chat — that puts the words back in a model's
hands, which is the thing this repo exists to avoid. Tell them what is missing
and let them supply the facts.

## The limits, which you should state

- A figure is found by looking for digits and a small set of worded quantities
  ("zero manual intervention", "two analysts"). A real outcome phrased with
  neither is missed.
- A skill counts as shown when its name, or the first word of a multi-word
  name, appears in the work. Spelling one differently in the bullets — "MEVN
  stack" for Vue and Express — reads as unshown, and that is worth saying
  aloud rather than treating as a fault.
- It reads the profile, not the PDF. Anything that only exists as a hyperlink
  in the original document is not there.
