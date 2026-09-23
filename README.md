# job-hunter

One command that prepares one job application, inside Claude Code.

```
/prep-apply https://boards.greenhouse.io/acme/jobs/42
```

It reads the posting, tells you how well your CV answers it **before** you
change anything, tailors the CV and writes a cover letter, tells you how much
that actually helped, critiques both, and works out who to message on LinkedIn.

**No API key.** Claude Code is the model, so your own subscription pays for it.
There is no provider to sign up to and no token bill.

**It never applies to anything.** It makes the documents. You send them.

---

## What you get

One directory per job:

```
runs/2026-09-23-acme-senior-data-engineer/
├── README.md         what is in here, and what to check before sending
├── fit-before.md     how your CV answered this job as it stood
├── cv.pdf  cv.md     the tailored CV, to attach or to paste
├── letter.pdf .md    the cover letter
├── fit-after.md      what the tailoring actually bought
├── critique.md       what is still weak in both
├── outreach.md       who to message, the searches to run, what to say
└── job.yaml          the posting, as read
```

## Setup

Four commands, once.

```bash
git clone https://github.com/mohamedaminehamdi/job-hunter && cd job-hunter
pip install -e .
playwright install chromium          # it drives a real browser to read job pages
git config core.hooksPath .githooks  # stops you ever committing your own CV
```

Then drop your CV into `cv/` — pdf, docx, txt, md, whatever it is called — open
Claude Code in this folder, and run `/prep-apply <url>`.

The first run reads your CV and writes `profile.yaml`, then **stops and asks you
to check it**. A model read your CV; you check it once, and everything after is
built on facts you have approved.

## Reading the fit score

The part worth understanding, because it is the part that tells you something.

```
Evidenced in your profile:    4 of 9   (unchanged by tailoring - it is what you have done)
  not checkable:              2        (judge these yourself)

Shown in the first screenful: 2 of 4  ->  4 of 4      +2
Present anywhere in the CV:   4 of 4  ->  4 of 4

Not evidenced anywhere in your profile:
  · OpenStack   "Experience running OpenStack in production"
  · German      "German B2 or above"
```

Two numbers, because they answer different questions.

**Evidenced** is how much of what this job asks for your *profile* can back. It
is a fact about you, and **it does not move when the CV is rewritten** — that is
deliberate. If a tailored CV could raise this number, the number would be
measuring how well the CV copies the posting, which is exactly the thing you do
not want it to reward.

**Shown** is how much of that a reader meets in the first screenful. This is the
one tailoring moves, and moving it is the whole job: the evidence was already
there, buried at bullet nine.

So a CV that pastes the job's requirements into its summary scores **zero** extra
and gets told off for it — that appears as *claimed but not evidenced*.

**Not checkable** is requirements like "strong communication skills". Nothing
concrete to look for, so they leave the denominator rather than being counted as
failures. You judge those.

A **gap** is a thing this job asks for that nothing in your profile backs. Two
honest responses: close it, or stop applying for jobs that need it. The one
response this tool will not help you with is claiming it anyway.

## Your profile is the source of truth

`profile.yaml`, at the repo root, next to your CV. Plain YAML — edit it by hand
whenever that is faster.

Two fields carry most of the weight. **Bullets** are the only material the
tailorer has: it selects, reorders and rewords them, and cannot write new ones.
**Skills** are what the fit score is measured against. A thin profile produces
thin documents, and no amount of prompting fixes that.

## How it avoids inventing things

The model never gets to write an employer, a title, a date, a degree or a
certification. It answers with *indices* into your profile, and those fields are
copied across verbatim — so a fabricated employer isn't something that gets
caught after the fact, it can't be expressed.

What is left is free text — a summary, reworded bullets, letter paragraphs — and
that is checked word by word against your profile. Figures and proper nouns that
appear nowhere in it are flagged:

```
[warning] summary: The figure '6' is not in your profile - check it before you send this.
```

The check reads English and French. It does not read languages that capitalise
every noun, German among them — there it says so once and leaves the reading to
you, rather than burying a correct letter under a hundred false findings.

## LinkedIn

It does not scrape LinkedIn. LinkedIn walls and throttles automated access, and
the risk of working around that lands on *your* account.

What it does instead: works out which roles at that company are worth a message
— alumni from your university first, because that is what actually gets replies
— builds the searches, and drafts something specific enough to answer. You run
the search and press send.

## What it deliberately does not do

- **Apply to anything.** Some employers disqualify applications that were not
  written by the applicant. That is their call, and honouring it is yours.
- **Search for jobs.** You bring the link. There are better job boards than
  anything this would be.
- **Track your applications**, beyond one line per run in `runs/log.md`. It is
  markdown; type what happened next into it.
- **Have a UI.** One command.

## When it goes wrong

| What you see | What it means |
|---|---|
| `Chromium cannot start` | `playwright install chromium` |
| `Only 300 characters came back` | The posting is behind a login wall. Paste the description when it asks — that path is fully supported |
| `No profile yet` | Put a CV in `cv/` and run it again |
| `This posting has no description` | Same: paste the text |
| The fit score says `0 of 0` | The posting stated no requirements, so it fell back to keywords. Coarser, and it says so |

## A word on honesty

This tool makes it easy to produce a polished CV quickly. It does not make it
safe to send one you haven't read.

Generated text can contain claims your profile doesn't support. It tries hard to
surface those — unfilled placeholders block export, the fit score names what you
cannot back, and the critique says what is weak — but the last check is yours.
Read what you send.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Tests: `pytest`. Lint: `ruff check src tests`.

## License

MIT — see [LICENSE](LICENSE).
