# Job Hunter

Self-hosted job application assistant. Give it your CV once; it tailors a CV, a
cover letter, and your application answers to each job you apply for.

Runs entirely on your machine. Your CV never leaves it except in the calls you
make to the model provider you choose — and that can be a local one.

> **Status: alpha, but complete end to end.** Import a CV, add a job, generate a
> tailored CV, cover letter and application answers, review them, export PDFs —
> from the CLI or the browser UI. Not yet on PyPI; install from source.

## Why

Most CV generators either fill a template with no judgement, or hand a language
model your CV and let it write whatever sounds impressive. The second kind
invents things — courses you never took, tools you never used — and you find out
when an interviewer asks.

Job Hunter separates the two problems. Your **profile** is facts, stored as plain
YAML you own and can edit. **Tailoring** is a generation step that reads those
facts and always shows you what it produced before anything is exported.

## Install

Not published yet, so install from a clone:

```bash
git clone https://github.com/mohamedaminehamdi/job-hunter && cd job-hunter
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e .
playwright install chromium    # used for PDF rendering and job-page fetching
```

Point it at a model. Any provider [LiteLLM](https://docs.litellm.ai/docs/providers)
supports works:

```bash
export JOB_HUNTER_MODEL=anthropic/claude-sonnet-5
export JOB_HUNTER_API_KEY=sk-ant-...
```

Or run it free and fully offline with [Ollama](https://ollama.com):

```bash
export JOB_HUNTER_MODEL=ollama/llama3.1
```

## Use

Two front ends over the same code: a browser UI and a CLI. Nothing is only in one
of them.

```bash
job-hunter doctor         # is everything wired up?
job-hunter serve          # the UI, on http://127.0.0.1:8765
```

`doctor` answers the three questions worth asking before anything else — can it
reach a model, can it start a browser, is there a profile to work from:

```
model     anthropic/claude-sonnet-5
          ready
browser   ready
home      /Users/you/.job-hunter
profile   ready (/Users/you/.job-hunter/profile.yaml)
jobs      3 saved
```

Everything lives in one directory you can read, edit and back up:

| Path | What it is |
|---|---|
| `~/.job-hunter/profile.yaml` | Your career facts. The source of truth for every generator |
| `~/.job-hunter/search.yaml` | What to look for, and where |
| `~/.job-hunter/queue.yaml` | Search results, their scores, and what you decided |
| `~/.job-hunter/jobs/*.yaml` | Postings you saved, as parsed |
| `~/.job-hunter/documents/*.yaml` | Generated CVs, letters and answers, before export |
| `~/.job-hunter/output/*.pdf` | The finished PDFs |
| `~/.job-hunter/llm_calls.jsonl` | Every model call, with tokens and cost |

Set `JOB_HUNTER_HOME` to keep more than one — a separate home per job hunt, or a
throwaway one to experiment in.

### 1. Get your profile in

Everything else reads from this, so it comes first. Three ways in, and you can
mix them freely.

**Import a CV.** PDF, DOCX, TXT or MD:

```bash
job-hunter import ~/cv.pdf
```

The text is extracted deterministically, then a model maps it onto the schema.
That second step is generation, so it can misread things — the UI says so, and
the extracted profile is yours to correct before you generate anything from it.
A scanned PDF with no text layer will be refused rather than half-read; paste the
text instead.

**Write the YAML.** Faster than fixing a bad extraction, and every field is
optional:

```yaml
personal:
  name: Ada
  surname: Lovelace
  headline: Backend Engineer
  email: ada@example.com
  phone: "+41 79 000 00 00"
  city: Zurich
  country: Switzerland
  github: https://github.com/ada
  linkedin: https://linkedin.com/in/ada
  website: ""

summary: Backend engineer with eight years building payment systems in Python and Go.

experience:
  - position: Senior Backend Engineer
    company: Numbers AG
    start: "2021-03"          # any format you like - printed as written
    end: Present
    location: Zurich
    industry: Fintech
    bullets:                  # the tailorer selects and rewords these
      - Cut p99 checkout latency from 1.8s to 240ms by replacing a synchronous
        ledger write with an append-only queue.
      - Led the migration of 40 services from Python 3.8 to 3.12 with zero downtime.
    skills: [Python, PostgreSQL, Kafka]

education:
  - level: MSc
    institution: ETH Zurich
    field_of_study: Computer Science
    start: "2015"
    end: "2017"
    grade: 5.5/6
    location: Zurich
    courses: [Distributed Systems, Compiler Design]

projects:
  - name: ledgerkit
    description: Open-source double-entry ledger library, 1.2k stars.
    link: https://github.com/ada/ledgerkit
    tech: [Python, SQLite]

skills: [Python, Go, PostgreSQL, Kafka, Kubernetes, Terraform]

certifications:
  - {name: CKA, issuer: CNCF, year: "2023", description: ""}

languages:
  - {name: English, level: Native}
  - {name: German, level: B2}
```

**Edit it in the browser.** The Profile page has the same YAML in a textarea,
with the problem checklist beside it.

However it got there, `job-hunter profile` tells you what is missing:

```
Ada Lovelace - 2 role(s), 1 degree(s)  [~/.job-hunter/profile.yaml]
3 thing(s) to look at:
  [x] personal.name: A name is required to render a CV.
  [!] personal.email: No email - employers cannot reply.
  [-] skills: Listing skills improves keyword matching.
```

`[x]` blocks export, `[!]` will make the output visibly worse, `[-]` is worth
getting to eventually. Loading a profile never fails — a half-finished one comes
back as this list, not an error.

Two things are worth filling in properly, because the rest of the tool leans on
them. **Bullets** are the only material the tailorer has: it selects and rewords
them, and cannot invent replacements. **Skills** are what job matching scores
against, and what the invention guard treats as supported.

### 2. Get a job in

Either add one you already found, or let a search find them.

#### One you already have

```bash
job-hunter job https://boards.greenhouse.io/acme/jobs/42
```

A headless browser loads the page — most boards render the description with
JavaScript, so a plain HTTP request would get you a spinner — the furniture is
stripped, and a model turns the text into fields: title, company, location,
requirements, responsibilities, keywords. It also reads the company's brand
colour off the page for the letter.

If the posting is behind a login, paste the text instead:

```bash
pbpaste | job-hunter job -              # or: job-hunter job --text "..."
```

`job-hunter jobs` lists what you have saved, with the slug each command wants.

#### Or search for them

Describe the search once, in `~/.job-hunter/search.yaml` or in the editor on the
Queue page:

```yaml
titles: [Backend Engineer, Platform Engineer]   # required

locations:                      # each one is searched separately
  - Zurich, Switzerland         # one entry, not two - see the note below
  - Remote

remote: true                  # a listing stating a workplace you set to false
hybrid: true                  # is dropped; one that states nothing is kept
onsite: true

posted_within_days: 60        # 0 for any age. An undated posting is never "old"
min_score: 45                 # what reaches the queue. Tune after the first run
limit_per_source: 25          # so one busy board cannot drown the others

company_blacklist: [Wayfair]  # matched anywhere in the field, case-insensitive
title_blacklist: [Sales, Frontend]
location_blacklist: [Brazil]

greenhouse: [anthropic, stripe]             # board slugs
lever: [acme]
ashby: [ramp]
pages: [https://example.com/careers]        # any page that lists jobs
linkedin: false                             # see the warning below
indeed: false
```

The board slug is the last part of the board's own URL —
`jobs.lever.co/`**`acme`**, `boards.greenhouse.io/`**`anthropic`**. There is no
global index of these, so the three board lists are a watchlist you build up.
`pages` is the catch-all for everything else: give it any URL that lists jobs — a
company's careers page, a board's search results — and it reads the posting links
off it with a browser.

Write `locations` as a block list, one place per line. `[Zurich, Switzerland]` on
one line is YAML for *two* locations, and a bare `Zurich` is what sends LinkedIn
to Ontario.

Then:

```bash
job-hunter search                      # all sources
job-hunter search --source greenhouse  # or one, repeatable
```

```
103 found, 11 queued, 11 new, 33 filtered out, 59 below score.
  greenhouse:anthropic          25 listing(s)
  ashby:ramp                    25 listing(s)
  page:https://...              3 listing(s)
  linkedin:Zurich Switzerland   25 listing(s)
  linkedin:Remote               25 listing(s)
```

Sources fail alone. A dead slug or a sign-in wall is reported on its own line and
the rest of the search carries on.

Every hit is scored against your profile — title match, which of your skills it
names, location, how recent — and what clears `min_score` lands in the queue with
its reasoning attached:

```bash
job-hunter queue --why
```

```
 80  cradle-backend-software-engineer-python-d296ad  Backend Software Engineer, Python at Cradle
       - Title matches 'Backend Engineer'.
       - Names your Python.
       - In Zurich, Switzerland.
       - Posted this week.
```

Scoring is deterministic — word overlap, no model call per hit. A sweep of twenty
boards costs nothing, the order does not shuffle between runs, and every score
can say where it came from. If the queue is full of the wrong jobs, the fix is in
`search.yaml`, and the reasons tell you which line to change.

**Nothing has been applied to, and nothing has been generated yet.** Two ways
out of the queue:

```bash
job-hunter pick cradle-backend-software-engineer-python-d296ad
job-hunter dismiss ramp-software-engineer-data-platform-26ad0e
```

Picking is what costs a page load and a model call: it fetches the full posting
and saves it as an ordinary job, ready to tailor. Dismissing is permanent —
later searches will find the same posting on three other boards and leave it
dismissed, because identity is the URL with its click-tracking stripped off.

Run `search` as often as you like. Decisions are never overwritten; scores and
listing details are refreshed underneath them.

> **Before you turn on `linkedin` or `indeed`.** Both prohibit automated access
> in their terms, and the risk is to your own account — that is why they default
> to false. In practice LinkedIn's logged-out search works and returns fewer
> results than you would see signed in; Indeed serves an anti-bot challenge to a
> headless browser more often than not, and says so rather than failing quietly.
> Qualify your cities with a country — `Zurich, Switzerland`, not `Zurich` —
> because LinkedIn's guest search resolves a bare city name badly and will
> happily answer with a different continent.

### 3. Tailor

```bash
job-hunter cv    cradle-backend-software-engineer
job-hunter letter cradle-backend-software-engineer --branded
job-hunter answer cradle-backend-software-engineer "Why do you want to work here?"
```

**`cv`** reorders your roles by relevance, picks the strongest bullets from each
and rewords them for this job, orders your skills, and writes a summary.

**`letter`** writes three short paragraphs in the language of the posting.
`--branded` uses the colour read off the company's page instead of neutral ink.

**`answer`** drafts one application-form answer. `--words 120` sets the limit. An
honest *no* is an allowed answer, and it will tell you separately when the
question asked about something your profile does not show. Answers are text to
paste into a form, so there is no PDF.

Both `cv` and `letter` take `--theme classic|neutral`. Each writes a YAML
document under `~/.job-hunter/documents/` — edit that by hand before exporting if
you want the last word on the wording.

### 4. Review, then export

Everything generated arrives with a checklist. In the browser, **Review** shows
the document, the issues, and a print-accurate preview side by side. On the CLI
they print after the document:

```
5 thing(s) to check before you send this:
  [!] paragraphs[1]: The figure '15' is not in your profile - check it before you send this.
  [!] paragraphs[1]: 'Cambridge' does not appear in your profile. Remove it, or add
                     it to your profile if it is true.
```

Add `--export` to write the PDF, or press **Export PDF** on the review page:

```bash
job-hunter cv cradle-backend-software-engineer --export --theme classic
```

PDFs land in `~/.job-hunter/output/`. A document with a blocking issue — an
unfilled placeholder, a missing name — will not export until it is fixed. Warnings
will not stop you; they are there to be read.

### Command reference

| Command | What it does |
|---|---|
| `doctor` | Model, browser, profile, job count |
| `import <file>` | CV in — pdf, docx, txt, md, yaml |
| `profile` | The saved profile and its problems |
| `search [--source X] [--timeout N]` | Run the sources, score, fill the queue |
| `queue [--why] [--all] [--status new\|picked\|dismissed]` | What was found |
| `pick <id>` | Queued listing → saved job |
| `dismiss <id>` | Drop it, for good |
| `job <url\|-> [--text] [--timeout N]` | Add a posting by hand |
| `jobs` | Saved postings and their slugs |
| `cv <slug> [--export] [--theme T]` | Tailored CV |
| `letter <slug> [--export] [--theme T] [--branded]` | Cover letter |
| `answer <slug> <question\|-> [--words N]` | One application answer |
| `serve [--host H] [--port P]` | The browser UI |

`--json` works on every command, for scripting.

### When something goes wrong

| What you see | What it means |
|---|---|
| `No API key for '...'` | Set `JOB_HUNTER_API_KEY`, or point `JOB_HUNTER_MODEL` at a local model |
| `Chromium cannot start` | `playwright install chromium` |
| `Only N characters came back` | A login wall or a late-rendering page. Paste the description text instead |
| `Only a fragment of this posting came through` | Same — the posting saved, but there is too little to tailor against |
| `has no extractable text` | A scanned CV. Paste the text, or write the YAML |
| `No board found ... check the slug` | The slug is not the company name — take it from the board's own URL |
| `LinkedIn showed a sign-in wall` | Intermittent for logged-out visitors. Try later, or use the company boards |
| `Indeed served its anti-bot challenge` | Expected. There is no way around it from a headless browser |
| Search finds a lot, queues nothing | Look at `queue --why` on a near miss, then lower `min_score` or widen `titles` |
| Jobs from the wrong country | Qualify the city with its country in `locations` |

## How it avoids inventing things

The model never gets to write an employer, a title, a date, a degree or a
certification. It answers with *indices* into your profile, and those fields are
copied across verbatim — so a fabricated employer isn't something that gets
caught after the fact, it can't be expressed. A skill the model adds that your
profile doesn't list is dropped, and it tells you it dropped it.

What's left is free text — a summary, reworded bullets, letter paragraphs — and
that's checked word by word against your profile. Figures and proper nouns that
appear nowhere in it are flagged for you to look at:

```
[warning] summary: The figure '6' is not in your profile - check it before you send this.
[warning] summary: 'Kubernetes' does not appear in your profile. Remove it, or add
                   it to your profile if it is true.
```

The check is lexical, not semantic. It misses a plausible reword and occasionally
flags something legitimate. It's a review aid, not a guarantee — see
[A word on honesty](#a-word-on-honesty).

**Languages.** A letter is written in the language of the posting, and the
wording check reads **English and French**. Figures are checked in any language —
`25,000`, `25 000` and `25.000` are the same number to it, so quoting an English
CV in a French letter doesn't raise a false alarm.

It does not read languages that capitalise every noun, German among them: the
check assumes a capitalised word mid-sentence is a name, which in German is every
second word. Rather than bury a correct letter under a hundred findings, it says
so once and leaves the reading to you:

```
[warning] paragraphs: This is written in 'de', and the wording check only reads
                      English and French - the figures above were checked, the
                      words were not. Read it against your profile yourself.
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `JOB_HUNTER_MODEL` | `anthropic/claude-sonnet-5` | Any LiteLLM model string |
| `JOB_HUNTER_API_KEY` | — | Your provider key. Not needed for local models |
| `JOB_HUNTER_API_BASE` | — | For Ollama or another self-hosted endpoint |
| `JOB_HUNTER_HOME` | `~/.job-hunter` | Where the profile, output and call log live |

Every model call is appended to `~/.job-hunter/llm_calls.jsonl` with token counts
and cost, so you can see what you're spending. The rest of what lives in the home
directory is listed [above](#use).

## Roadmap

- [x] Profile model, validation-as-warnings, YAML storage
- [x] CV intake — PDF / DOCX / text / YAML
- [x] Provider-agnostic model layer with cost logging
- [x] Job fetching from a URL, and job modelling
- [x] Tailored CV generation, with the invention guard
- [x] Tailored cover letter, neutral and company-branded
- [x] Application question answering
- [x] CLI over the whole flow
- [x] Web UI, with the review step at its centre
- [x] Job discovery — multi-source search, scoring, and a review queue
- [x] English and French throughout — letters, answers, dates, the invention guard
- [ ] Assisted application — filling a posting's form from the tailored
      documents, with the submit button still yours to press

## A word on honesty

This tool makes it easy to produce a polished CV quickly. It does not make it
safe to send one you haven't read.

Generated text can contain claims your profile doesn't support. Job Hunter tries
hard to surface those — unfilled placeholders block export, and the review step
shows you the output before it becomes a document — but the last check is yours.
Read what you send.

Some employers also require that applications be your own words and disqualify
AI-written ones. That's their call to make, and it's on you to honour it.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Tests: `pytest`. Lint: `ruff check src tests`.

## License

MIT — see [LICENSE](LICENSE).
