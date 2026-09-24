# jobhunt — for Claude Code

Everything is in [AGENTS.md](AGENTS.md), which is written for every harness
including this one. Read that.

Two things specific to Claude Code:

**The skills are a plugin.** From this repo you can load them directly:

```
/plugin marketplace add mohamedaminehamdi/job-hunter
/plugin install jobhunt@jobhunt
```

Then `jobhunt <job-url>` runs the whole flow, or ask for any one skill by
what you want — each `SKILL.md` describes when it applies.

**Without installing**, the skills are plain files. Read
`plugins/jobhunt/skills/<name>/SKILL.md` and follow it; the scripts beside
them need no key and no install.
