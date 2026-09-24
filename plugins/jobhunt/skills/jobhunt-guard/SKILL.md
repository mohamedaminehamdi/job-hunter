---
name: jobhunt-guard
description: >
  Check any piece of writing against the facts in a profile and flag figures
  and proper nouns it cannot back. Use when someone wants to know whether a CV,
  letter, bio or answer claims something they cannot support.
allowed-tools: Bash, Read
---

# Check it against the facts

```bash
python3 guard.py "The text to check"
python3 guard.py --file draft.md
cat draft.md | python3 guard.py
```

Options: `--profile <path>`, `--language fr`, `--allow "Acme, Senior Engineer"`
for words that are fair to use (a company name you are writing to),
`--asked "the question"` when the text is answering one.

## What it does

Compares the words and figures in the text against the words and figures in
the profile. Anything that looks like a claim - a figure, an acronym, a
capitalised word mid-sentence - and is not in the profile gets flagged.

## What it does not do

It is **lexical, not semantic**. It cannot tell a denial from a boast, and it
does not pretend to: "I have never used Kafka" and "I am an expert in Kafka"
both flag Kafka. It also misses a plausible-sounding rewording that invents
nothing lexically new.

So it is a review aid. Every finding is a sentence for the person to read
again, not an error and never a reason to rewrite silently.

It reads **English and French**. German capitalises every noun, so the
proper-noun check would report the whole document; there it says so once,
checks the figures, and leaves the wording to the reader. That is deliberate -
a hundred false findings buries the one real one.

## Relaying findings

Quote the finding and the sentence it is about. Then say which of the three it
is:

- **a real invention** - fix the text
- **true but not in the profile** - add it to the profile
- **a false positive** - say so and move on

Do not present all three as equally likely. Usually you know which it is.
