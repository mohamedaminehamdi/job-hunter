# Contributing

## Setup

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
```

## Architecture

Four packages with one job each. Keep the boundaries:

| Package | Owns | May not |
|---|---|---|
| `profile/` | The user's facts, validation, YAML storage | know about jobs or rendering |
| `jobs/` | Fetching and modelling a job posting | touch the profile |
| `generate/` | Every model call, via `generate/llm.py` | render HTML or PDF |
| `render/` | Jinja → HTML → PDF, themes | call a model |

`web/` is a thin layer over those. **No business logic in routes.**

`generate/llm.py` is the only module that talks to a provider. If you need a new
model capability, add it there rather than importing `litellm` elsewhere.

## Rules that exist for a reason

**Loading a profile must never raise.** Intake produces partial and messy data;
the UI shows problems as a checklist. Add checks to `Profile.report()`, not new
exceptions.

**Generators must not invent.** A generator may select, reorder and reword facts
from the profile. It may not add employers, dates, courses, tools or metrics that
are absent from it. If you loosen a prompt, add a test that pins the boundary.

**Every non-trivial change ships a test.** Especially parsing and prompt-output
handling — models return fenced JSON, prose-wrapped JSON, and truncated JSON, and
each of those has already broken something here.

## Style

PEP 8, `ruff check src tests`, line length 100. Docstrings on public functions
saying what and why, not restating the signature.
