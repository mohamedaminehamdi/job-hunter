---
name: jobhunt-posting
description: >
  Read a job posting from a URL (or pasted text) into job.yaml - title,
  company, requirements, and the page text it came from. Use when someone gives
  a job link and you need the posting as structured data.
argument-hint: <job-url>
allowed-tools: Bash, Read, Write
---

# Read the posting

Two steps, because only one needs judgement.

The script is next to this file -
`${CLAUDE_PLUGIN_ROOT}/skills/jobhunt-posting/posting.py` under a plugin install.

**Do not use `WebFetch`.** Greenhouse, Lever and Workday render descriptions
client-side; `WebFetch` gets a loading spinner. This loads the page in the
browser already on the machine.

## 1. Load the page

```bash
python3 posting.py "https://boards.greenhouse.io/acme/jobs/42"
```

It prints the run directory. Read `page.txt` from it.

**Exit 1?** The posting is behind a login wall, or the page gave back almost
nothing. Ask for the description as text and use it:

```bash
python3 posting.py --text pasted.txt "https://the-original-url"
```

Never work around a wall. Working around it means inventing a job description,
and everything downstream is then tailored to something imaginary.

## 2. Write what you read

Write JSON to a file, then parse it. Every field is optional; leave out what
the posting does not say rather than inferring it.

```json
{
  "title": "Senior Data Engineer",
  "company": "Acme",
  "location": "Munich, Germany",
  "workplace": "hybrid",
  "employment_type": "Full-time",
  "salary": "70-85k EUR",
  "language": "en",
  "description": "What the role is, in a paragraph or two.",
  "responsibilities": ["Own the ingestion pipelines"],
  "requirements": ["3+ years with Python", "Strong SQL"],
  "nice_to_have": ["Kafka"],
  "keywords": ["Python", "SQL", "dbt"]
}
```

```bash
python3 posting.py --parse job.json --run <run>
```

The run is renamed to `<date>-<company>-<role>` once the job has a name, and
the new path is printed. Use that path from then on.

## Getting it right

- **`requirements` is the field that matters.** It is what fit is scored
  against. One requirement per entry, in the posting's own words - do not merge
  two into one or split one into two.
- **Keep `required` and `nice_to_have` apart** as the posting divides them.
- **`language`** is the language the posting is written in, as a two-letter
  code. The letter is written in it, and the invention guard reads only English
  and French - it needs to know when it cannot check.
- **Do not paraphrase a requirement into something the candidate has.** That is
  the failure this whole tool exists to prevent, and it starts here.
- `url`, `brand_color` and `fetched_at` are filled in from what was observed.
  Anything you write for them is ignored.
