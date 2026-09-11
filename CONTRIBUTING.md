# Contributing

## Setup

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e ".[dev]"
playwright install chromium   # the renderer and the job fetcher drive a real browser
pytest
```

CI runs `ruff check src tests` and `pytest` on 3.11 and 3.12, and separately
builds a wheel and installs it somewhere with no source tree — the Jinja
templates are package data, and an editable install hides it when they go
missing.

## Architecture

Five packages with one job each. Keep the boundaries:

| Package | Owns | May not |
|---|---|---|
| `profile/` | The user's facts, validation, YAML storage | know about jobs or rendering |
| `discover/` | Searching sources, scoring hits, the queue | call a model, or fetch a posting |
| `jobs/` | Fetching and modelling a job posting | touch the profile |
| `generate/` | Every model call, via `generate/llm.py` | render HTML or PDF |
| `render/` | Jinja → HTML → PDF, themes | call a model |

`discover/` is deliberately the cheap half: its scoring is lexical, so a sweep
of twenty boards costs nothing and the order does not shuffle between runs. The
expensive work — a page load and a model call — happens once, when a listing is
picked. A source that fails is recorded against itself and the search carries on.

Each package persists what it owns: `profile/store.py`, `discover/store.py`,
`jobs/store.py`, `generate/store.py`. `render/` owns one piece of policy — a document with a
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

**Every non-trivial change ships a test.** Especially parsing and prompt-output
handling — models return fenced JSON, prose-wrapped JSON, and truncated JSON, and
each of those has already broken something here.

## Style

PEP 8, `ruff check src tests`, line length 100. Docstrings on public functions
saying what and why, not restating the signature.
