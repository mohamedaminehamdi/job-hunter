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

```bash
job-hunter doctor         # is the model reachable, is Chromium installed
job-hunter serve          # the browser UI, on http://127.0.0.1:8765
```

1. **Import your CV** — PDF, DOCX, plain text, or YAML. Anything that isn't
   already structured goes through a model, so you review the extraction before
   it's saved.
2. **Add a job** — paste a URL or the description text.
3. **Generate** — tailored CV and cover letter, with the cover letter in either
   neutral styling or the company's colours.
4. **Review, then export** — nothing becomes a PDF until you've seen it.

Your profile lives at `~/.job-hunter/profile.yaml`. It's plain YAML: edit it by
hand whenever that's faster than the UI.

### From the command line

Everything the UI does, the CLI does — same code underneath.

```bash
job-hunter import ~/cv.pdf                  # -> ~/.job-hunter/profile.yaml
job-hunter profile                          # what is there, and what is missing

job-hunter job https://boards.../jobs/42    # fetch, parse, save
pbpaste | job-hunter job -                  # or paste the description instead
job-hunter jobs                             # list saved jobs and their slugs

job-hunter cv zeta-senior-data-engineer --export
job-hunter letter zeta-senior-data-engineer --branded --export
job-hunter answer zeta-senior-data-engineer "Why do you want to work here?"
```

Add `--json` to any command for machine-readable output. PDFs land in
`~/.job-hunter/output/`.

### How it avoids inventing things

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

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `JOB_HUNTER_MODEL` | `anthropic/claude-sonnet-5` | Any LiteLLM model string |
| `JOB_HUNTER_API_KEY` | — | Your provider key. Not needed for local models |
| `JOB_HUNTER_API_BASE` | — | For Ollama or another self-hosted endpoint |
| `JOB_HUNTER_HOME` | `~/.job-hunter` | Where the profile, output and call log live |

Every model call is appended to `~/.job-hunter/llm_calls.jsonl` with token counts
and cost, so you can see what you're spending.

Generated documents are kept as YAML next to the profile, under
`~/.job-hunter/jobs/` and `~/.job-hunter/documents/`, so a review survives a
restart and you can edit a document before exporting it.

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
- [ ] Job discovery

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
