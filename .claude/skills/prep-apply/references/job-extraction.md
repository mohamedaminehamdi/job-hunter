# Reading the job posting

Ported verbatim from the job parser. `skill job` validates what you write and
overrides the URL, the brand colour and the fetch time with what was actually
observed, so those are not yours to guess.

## The rules

You extract structured data from job postings.

Rules:
- Copy requirements and responsibilities close to verbatim. Do not soften or embellish them.
- Never invent. If the posting does not state something, leave that field empty.
- Do not infer a salary, a seniority level or a location that is not written down.
- Distinguish hard requirements from nice-to-haves only where the posting itself does;
  when it does not, treat everything stated as a requirement.
- Ignore page furniture: cookie notices, similar jobs, application instructions,
  benefits lists and legal statements.
- Write only JSON matching the requested shape to the file you are told to.
  No prose, no code fences.

## Write exactly this shape

```json
{
  "title": "",
  "company": "",
  "location": "",
  "workplace": "",
  "employment_type": "",
  "salary": "",
  "description": "",
  "responsibilities": [""],
  "requirements": [""],
  "nice_to_have": [""],
  "keywords": [""],
  "language": ""
}
```

## Field notes:
- workplace: remote, hybrid or on-site, only if stated.
- description: two or three sentences on what the role is. Not a sales pitch for the company.
- keywords: the concrete tools, languages and domain terms this posting screens for.
- language: ISO 639-1 code of the language the posting is written in, e.g. "en", "fr".

## Why this matters more than it looks

Everything downstream reads these fields. `requirements` is what the fit score
is measured against, so a requirement you drop is a gap the candidate never
learns about, and a requirement you invent is one they will try to answer for.
Copy them close to verbatim, in the posting's own language.
