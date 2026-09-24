# job-hunter

This repository prepares **one job application** from a job URL: it reads the
posting, scores how well the user's CV answers it before and after tailoring,
writes a tailored CV and cover letter, critiques them, and drafts LinkedIn
outreach.

It **applies to nothing and submits nothing.**

**Read [`AGENTS.md`](../AGENTS.md) in the project root and follow it.** That file
has the procedure, the exit codes, the prohibitions, and the tool-name mapping.

The short version: the exact half is a plain CLI —
`python -m job_hunter.skill <verb>` — and your job is the judgement, written to
four JSON files. Never write `cv.md` or `letter.md` yourself; never invent a
claim the user's profile does not back; never apply to anything.
