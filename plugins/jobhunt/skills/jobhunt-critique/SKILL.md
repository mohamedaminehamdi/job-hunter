---
name: jobhunt-critique
description: >
  Read a finished CV and cover letter against the posting and the fit score and
  say what is still weak, before anything is sent. Use as the last check on an
  application.
allowed-tools: Bash, Read, Write
---

# Critique it

```bash
python3 critique.py --run <run>          # prints everything to read
python3 critique.py --run <run> --write critique.md
```

The first call prints the posting, the CV, the letter and the fit report, so
the critique is written against the documents rather than from memory.

## What to look for

1. **Claims the profile does not back.** Any open guard finding, and anything
   in `parroting`. These are the ones that matter - the rest is style.
2. **The opening.** Would a reader keep going after the summary and the first
   two bullets? That is all most get.
3. **Evidence that is buried.** Something in `regressions`, or a strong bullet
   sitting at position six.
4. **Bullets that describe duties rather than outcomes.** "Responsible for the
   pipelines" against "Cut ETL runtime 35%".
5. **The letter's specificity.** Could it be sent to another company with the
   name changed? Then it says nothing.
6. **Real gaps.** Name them. The candidate is deciding whether to spend an hour
   on this application.

## How to write it

**Be direct and be specific.** "The summary is generic" is useless. "The
summary says 'passionate about data' and never mentions the 25,000-device
fleet, which is the strongest thing here" is useful.

Do not open with what is working. If something is genuinely strong, one line.
The value of this step is the part that is wrong, and a critique that leads
with praise gets skimmed past the part worth reading.

Do not suggest adding anything the profile does not contain.
