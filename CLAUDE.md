# job-hunter

This repo is a Claude Code skill. Open it and run:

```
/prep-apply <job-url>
```

It prepares one job application end to end — reads the posting, scores how well
the CV answers it before and after tailoring, writes a tailored CV and cover
letter, critiques them, and drafts LinkedIn outreach. It applies to nothing.

The skill is `.claude/skills/prep-apply/SKILL.md`; its rules are in
`references/` beside it. **If you are working on this repo** rather than using
it, read [CONTRIBUTING.md](CONTRIBUTING.md) — particularly that there is no
model in this codebase, and why `assemble()` is the reason an invented employer
cannot be expressed.

Other agents (Codex, Copilot, Cursor, Cline, Aider) use [AGENTS.md](AGENTS.md).
