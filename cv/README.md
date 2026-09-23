# Put your CV here

Any of: `.pdf`, `.docx`, `.txt`, `.md`, `.yaml`. Keep the name it already has —
`Resume_v3_FINAL.pdf` is fine, nothing here cares.

The first time you run `/prep-apply`, Claude reads whatever is in this folder
and writes `profile.yaml` at the repo root. That profile is the source of truth
for every document this tool will ever build for you, so check it once — it was
produced by a model reading a PDF.

Everything in this folder except this file is gitignored, and a pre-commit hook
refuses to commit it. Your CV is yours.
