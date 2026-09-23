# Reading the candidate's CV

Ported verbatim from `profile/intake.py`. Runs once, the first time someone uses
this repo. `skill profile --cv <file>` extracts the text deterministically; you
map that text onto the schema.

## The rules

You extract structured data from CVs.

Rules:
- Copy facts verbatim wherever possible. Do not rephrase achievements.
- Never invent. If a field is absent from the CV, leave it empty.
- Do not add courses, skills, dates or employers that are not written in the text.
- Write only JSON matching the requested shape to the file you are told to.
  No prose, no code fences.

## Write exactly this shape, as YAML, to `profile.yaml`

```json
{
  "personal": {"name":"","surname":"","headline":"","email":"","phone":"",
               "city":"","country":"","github":"","linkedin":"","website":""},
  "summary": "",
  "experience": [{"position":"","company":"","start":"","end":"","location":"",
                  "industry":"","bullets":[""],"skills":[""]}],
  "education": [{"level":"","institution":"","field_of_study":"","start":"",
                 "end":"","grade":"","location":"","courses":[""]}],
  "projects": [{"name":"","description":"","link":"","tech":[""]}],
  "skills": [""],
  "certifications": [{"name":"","issuer":"","year":"","description":""}],
  "languages": [{"name":"","level":""}]
}
```

## After you write it

Run `python -m job_hunter.skill profile --normalise`, show the candidate the
report, and **stop**. This profile is the source of truth for every document
this tool will ever build for them, and it was produced by a model reading a
PDF. They check it before anything is built on it.
