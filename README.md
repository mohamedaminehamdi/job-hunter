# Job Hunter

Self-hosted job application assistant. Give it your CV once; it tailors a CV, a
cover letter, and your application answers to each job you apply for.

Runs entirely on your machine. Your CV never leaves it except in the calls you
make to the model provider you choose — and that can be a local one.

> **Status: alpha.** The profile layer is built and tested. Tailoring, the review
> UI, design modes, and question answering are in progress. See [Roadmap](#roadmap).

## Why

Most CV generators either fill a template with no judgement, or hand a language
model your CV and let it write whatever sounds impressive. The second kind
invents things — courses you never took, tools you never used — and you find out
when an interviewer asks.

Job Hunter separates the two problems. Your **profile** is facts, stored as plain
YAML you own and can edit. **Tailoring** is a generation step that reads those
facts and always shows you what it produced before anything is exported.

## Install

```bash
pip install job-hunter
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
job-hunter serve          # opens the browser UI
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

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `JOB_HUNTER_MODEL` | `anthropic/claude-sonnet-5` | Any LiteLLM model string |
| `JOB_HUNTER_API_KEY` | — | Your provider key. Not needed for local models |
| `JOB_HUNTER_API_BASE` | — | For Ollama or another self-hosted endpoint |
| `JOB_HUNTER_HOME` | `~/.job-hunter` | Where the profile, output and call log live |

Every model call is appended to `~/.job-hunter/llm_calls.jsonl` with token counts
and cost, so you can see what you're spending.

## Roadmap

- [x] Profile model, validation-as-warnings, YAML storage
- [x] CV intake — PDF / DOCX / text / YAML
- [x] Provider-agnostic model layer with cost logging
- [ ] Job fetching from a URL
- [ ] Tailored CV generation
- [ ] Tailored cover letter, neutral and company-branded
- [ ] Review UI — see the output beside your profile before exporting
- [ ] Application question answering
- [ ] Web UI
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
