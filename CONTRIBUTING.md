# Contributing

## Setup

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e ".[dev]"
playwright install chromium   # the renderer and the job fetcher drive a real browser
git config core.hooksPath .githooks
pytest
```

CI runs `ruff check src tests` and `pytest` on 3.11 and 3.12, and separately
builds a wheel and installs it somewhere with no source tree — the Jinja
templates are package data, and an editable install hides it when they go
missing.

## Architecture

**There is no model in this codebase.** Claude Code is the model; it writes four
JSON files per run and Python reads them. That is the single most important thing
to know before changing anything here: if you find yourself wanting to call an
API, the answer is a reference file in `.claude/skills/prep-apply/references/`.

Six packages with one job each. Keep the boundaries:

| Package | Owns | May not |
|---|---|---|
| `profile/` | The user's facts, validation, YAML storage | know about jobs or rendering |
| `jobs/` | Fetching and modelling a job posting | touch the profile |
| `fit/` | Measuring a CV against a job | look for evidence anywhere but the profile |
| `generate/` | Assembling documents, and the invention guard | render HTML or PDF |
| `render/` | Jinja → HTML → PDF, markdown, themes | make a judgement |
| `outreach/` | Who to message and the searches that find them | scrape anything |
| `skill/` | The nine verbs Claude Code runs | contain logic of its own |

`fit/` has one rule and everything depends on it: **evidence is looked for in the
profile and nowhere else.** A document decides what is *shown*; it cannot create
a fact. `guard.Support.of(job)` must never appear in that package — a posting
asking for Kafka does not license claiming it.

`skill/verbs/*` are thin on purpose. Each reads files, calls one library
function, writes into a run directory, prints a line of JSON and returns an exit
code. If a verb starts making decisions, the decision belongs in a package or in
SKILL.md. `render/` owns one piece of policy — a document with a
blocking issue does not become a file, enforced in `render.export` so no caller
can skip it.

`web/` is a thin layer over those. **No business logic in routes.** Its endpoints
are deliberately sync `def`, not `async def`: Starlette runs those in a worker
thread, and Playwright's sync API needs a thread with no running event loop.
Making a route async breaks job fetching and PDF export at runtime.

`generate/llm.py` is the only module that talks to a provider. If you need a new
model capability, add it there rather than importing `litellm` elsewhere.

## Rules that exist for a reason

**Loading a profile must never raise.** Intake produces partial and messy data;
the UI shows problems as a checklist. Add checks to `Profile.report()`, not new
exceptions.

**Generators must not invent.** A generator may select, reorder and reword facts
from the profile. It may not add employers, dates, courses, tools or metrics that
are absent from it. If you loosen a prompt, add a test that pins the boundary.

Prefer making that structural over checking for it afterwards. `generate/cv.py`
is the pattern: the model answers with *indices* into the profile and rewritten
bullet text, and every identity field is copied from the profile, so an invented
employer cannot be expressed rather than being caught later. Free text that a
model does write goes through `generate/guard.py`, which is lexical and therefore
fallible — it produces warnings for the user, never a silent rewrite. Keep the
job's requirements out of a document's support vocabulary: a posting asking for
Kafka must never license claiming it.

**Every non-trivial change ships a test.** Especially parsing — a JSON file a
model wrote arrives fenced, prose-wrapped or truncated exactly as often as an API
response did, which is why `generate/parsing.py` outlived the thing it was
written for.

**Change a shape in `references/*.md` and `tests/test_skill_contract.py` will
tell you.** It asserts the documented JSON keys are exactly the keys `assemble()`
reads, in both directions, and that the honesty rules are still in the reference
files word for word. If you change `assemble()`, change the reference.

**The markdown is written before the PDF is attempted.** Not a style choice: if
rendering fails and no document exists, the obvious next move is to let the model
write the markdown, which hands the employers and dates back to it. Keep that
ordering.

## Before you push

`ruff check src tests` and `pytest` cover everything but judgement. The half a
test cannot reach needs four minutes by hand:

1. a fresh clone, `pip install -e .`, `playwright install chromium`
2. a CV in `cv/`, then `/prep-apply` on a Greenhouse URL — it should work start
   to finish
3. `/prep-apply` on a LinkedIn URL — it should hit the wall and offer the paste
   path, which is the most common real failure
4. read the before/after: are the gaps real, and did `evidenced` stay put?

Nobody can automate the Claude Code half, and a mock would only test the mock.

## Style

PEP 8, `ruff check src tests`, line length 100. Docstrings on public functions
saying what and why, not restating the signature.
