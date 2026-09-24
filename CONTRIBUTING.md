# Contributing

## Running it

```bash
git clone https://github.com/mohamedaminehamdi/job-hunter && cd job-hunter
pip install -e ".[dev]"          # pytest, ruff, and pyyaml as a test oracle
git config core.hooksPath .githooks
pytest
```

Nothing that ships needs any of those. The skills are standard library only —
that is the product, not an aesthetic.

## The two rules that are not obvious

**`core/jobhunt.py` is the only place to edit the library.** The eleven
`plugins/jobhunt/skills/*/lib/jobhunt.py` are generated from it by
`python tools/sync.py`, and a test fails if one has drifted. The duplication is
deliberate: skills are installed one at a time, and a skill importing from a
sibling would work here and break the moment someone installs it alone.

**Standard library only, on Python 3.9.** That is what macOS ships, which is
what a friend on a fresh laptop has. `tests/test_core.py` carries an explicit
import allowlist and an AST check — adding a dependency should be a decision,
not something a test waves through. Note that ruff's `target-version` is
pinned to `py39` for the same reason: with `py311` it rewrites `timezone.utc`
to `datetime.UTC` and every skill stops importing on a stock Mac.

## Before you push

```bash
pytest
ruff check core plugins tools tests
python tools/sync.py                 # if you touched core/
python tools/build_site.py           # if you touched a SKILL.md
python tools/build_archives.py       # if you touched any skill
shellcheck -s sh install.sh          # if you touched the installer
```

CI runs all of it on Ubuntu and macOS, on 3.9 and 3.13, and fails on anything
stale.

## Adding a skill

1. `plugins/jobhunt/skills/jobhunt-<name>/SKILL.md`, with frontmatter that says
   **when to use it**, not only what it is — that description is all an agent
   sees before deciding to load it, and one that only describes never gets
   picked. A test checks for it.
2. The script beside it, ending with `raise SystemExit(jh.run_cli(work))` so
   the exit codes mean the same thing as everywhere else.
3. `python tools/sync.py` to give it the library.
4. Add it to `tools/site/data.py` — `ORDER`, `HEADLINES`, `PLAIN` — and to
   `SKILLS` in `install.sh`. Tests fail if you forget either.

## How the tests are organised

| | |
|---|---|
| `test_core.py` | what replaced pydantic, Jinja, playwright and pypdf |
| `test_yaml.py` | the YAML subset, one test per bug pyyaml caught |
| `test_guard.py` | the invention guard, including what it must *not* flag |
| `test_fit.py` | the two numbers, and that only one of them can move |
| `test_run.py` | one whole application, through the scripts as subprocesses |
| `test_contract.py` | where a SKILL.md and its script have to agree |
| `test_skills.py` | packaging: drift, and each skill installed alone |
| `test_install.py` | the installer, run the way a person runs it |
| `test_site.py` | the page and the download archives |

When a test's name reads like a sentence about behaviour, keep it that way.
The point of `test_evidenced_is_identical_before_and_after` is that someone
reading the failure knows what broke without opening the file.

## Style

- Comments say **why**, not what. If a line needs a comment to say what it
  does, the line is the problem.
- A comment that explains a bug should say what the bug *was* — several in
  here are the only record of a failure that took an hour to find.
- English, and PEP 8. Docstrings on new functions and classes.

## Never commit

`jobhunt/`, `cv/`, `runs/` or `profile.yaml`. Those are somebody's career and
their contact details. Three layers say no — `.gitignore`, the pre-commit hook,
and a CI job — and all three exist because `.gitignore` alone is advice and
`git add -f` is one keystroke.
