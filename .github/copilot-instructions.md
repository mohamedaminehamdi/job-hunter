# jobhunt — for GitHub Copilot

The full instructions are in [AGENTS.md](../AGENTS.md). Read that file.

In short: this repo is eleven skills for preparing job applications. Each lives
in `plugins/jobhunt/skills/<name>/` with a `SKILL.md` saying when to use it and
a Python script beside it that needs no API key and nothing installed.

Four rules hold wherever you enter, and they are the same four in
[AGENTS.md](../AGENTS.md):

1. **Never apply to anything.** Produce the documents; the person sends them.
2. **Never invent.** Every claim traces to their profile.
3. **Never write `cv.md` or `letter.md` yourself.** They are rendered from
   `cv.yaml`; writing one by hand hands the employers and dates back to a model.
4. **Never work around a login wall.** Ask for the description as text instead.
