# jobhunt — instructions for any coding agent

This repo is a set of **eleven skills** for preparing job applications, plus
the tooling that builds and ships them. It is read by OpenAI Codex, Cursor,
Cline, Aider, Gemini CLI, Windsurf and anything else that picks up
`AGENTS.md`; Claude Code reads [CLAUDE.md](CLAUDE.md), which says the same
thing.

There are two reasons to be in this repo, and they need different things.

---

## 1. Someone wants to use it, and has this folder open

The skills are in `plugins/jobhunt/skills/`. Each is a directory with a
`SKILL.md` and, usually, one Python script beside it.

**Read the SKILL.md of the skill that matches the request and follow it.**
Start here:

| They want | Read |
|---|---|
| a whole application prepared from a job link | `plugins/jobhunt/skills/jobhunt/SKILL.md` |
| their CV turned into a profile | `.../jobhunt-profile/SKILL.md` |
| to know how well they match a job | `.../jobhunt-fit/SKILL.md` |
| a CV tailored to one posting | `.../jobhunt-tailor/SKILL.md` |
| a cover letter | `.../jobhunt-letter/SKILL.md` |
| any writing checked against their CV | `.../jobhunt-guard/SKILL.md` |
| help answering an application question | `.../jobhunt-answer/SKILL.md` |
| to know who to message about a role | `.../jobhunt-outreach/SKILL.md` |

The scripts need **no API key, no install, and no arguments beyond what their
SKILL.md shows**. Standard library only, Python 3.9+. Run them with `python3`.

Their files go in `jobhunt/` in the working directory — profile, CV, and one
folder per job. Nothing else is written and nothing is uploaded.

### The four rules, wherever you enter

1. **Never apply to anything.** Produce the documents; the person sends them.
2. **Never invent.** Every claim traces to their profile. A skill they do not
   have is not yours to solve — say so.
3. **Never write `cv.md` or `letter.md` yourself.** They are rendered from
   `cv.yaml`. Writing one by hand hands the employers, titles and dates back
   to a model, which is the one thing this repo exists to prevent.
4. **Never work around a login wall.** If a posting comes back thin, ask for
   the description as text. Working around the wall means inventing the job.

Exit codes are the same in all eleven: `0` fine, `1` the **user** must fix
something (stop and relay it), `2` the draft is not fit to send (rewrite the
JSON, once), `3` your JSON could not be read (write it again, once).

---

## 2. Someone is working on the repo itself

### The shape of it

```
core/jobhunt.py                  the whole deterministic half, one file
plugins/jobhunt/skills/<name>/
    SKILL.md                     the judgement half: instructions for a model
    <name>.py                    the exact half: argv in, JSON out
    lib/jobhunt.py               a copy of core/jobhunt.py
tools/sync.py                    maintains those copies
tools/build_site.py              docs/index.html, from the skills themselves
tools/build_archives.py          docs/download/*.zip
install.sh                       POSIX sh, every install route
```

### The two rules that are not obvious

**`core/jobhunt.py` is the only place to edit the library.** Every
`lib/jobhunt.py` is generated from it by `python tools/sync.py`, and a test
fails if any has drifted. The duplication is deliberate: skills are installed
one at a time, and a skill that imported from a sibling would work here and
break the moment someone installs it alone.

**It is standard library only, and it must run on Python 3.9.** That is what
macOS ships. There is an explicit import allowlist and an AST check in
`tests/test_core.py`; adding a dependency should be a decision, not something
a test waves through.

### Before you push

```bash
pytest                                  # 373 tests
ruff check core plugins tools tests
python tools/sync.py                    # if you touched core/
python tools/build_site.py              # if you touched a SKILL.md
python tools/build_archives.py          # if you touched any skill
shellcheck -s sh install.sh
```

CI runs all of it on Ubuntu and macOS, on 3.9 and 3.13.

### Never commit

`jobhunt/`, `cv/`, `runs/` or `profile.yaml`. Those are somebody's career and
their contact details. Three layers say no — `.gitignore`, `.githooks/pre-commit`,
and a CI job — and all three exist because `.gitignore` alone is advice.
