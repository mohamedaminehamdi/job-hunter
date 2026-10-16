---
name: jobhunt-find
description: >
  List the openings on a company's Greenhouse or Lever careers board and rank
  them by how many of the profile's own skills each posting names, so the ones
  worth reading properly come first. Use when someone asks which jobs at a
  company fit them, wants a careers page scanned, or asks what is worth
  applying to before they have a link.
argument-hint: <greenhouse:token | lever:token | careers URL> [...]
allowed-tools: Bash, Read
---

# Find the openings worth an evening

Greenhouse and Lever publish every board's openings as public JSON. This reads
that - no browser, no login, nothing scraped - and ranks the openings by how
many of the profile's listed skills each one names.

```bash
python3 find.py greenhouse:figma
python3 find.py lever:palantir --title engineer --min 3
python3 find.py https://job-boards.greenhouse.io/gitlab greenhouse:cloudflare
```

It writes `jobhunt/found/<date>-<board>.md` and prints it, and beside it
`<date>-<board>.json`: the same list as data - each opening's title, link,
location and the skills it names, without the posting text. Read the page with
the person, and hand the URL they pick to `jobhunt-posting`.

The count at the top is every opening that names at least `--min` of the
profile's skills; `--limit` (50 by default) only cuts how many are listed.

`--title` is a plain substring, case-insensitive: `intern` also keeps
"Internal Audit", so `internship` is the tighter filter. `--min` is how many
of the profile's skills a posting must name to be listed at all.

## Naming a board

The token is the part of the careers URL after the host:
`boards.greenhouse.io/figma`, `job-boards.greenhouse.io/gitlab`,
`jobs.lever.co/palantir`. A careers page on a company's own domain usually
links to one of these - look at any job link on it: `gh_jid=` means
Greenhouse, `lever.co` means Lever. EU boards (`job-boards.eu.greenhouse.io`,
`jobs.eu.lever.co`) and Greenhouse embed links (`...?for=figma`) work pasted
as they are. A bare name (`figma`) is tried on both hosts.

**Exit 1?** Relay the message. A 404 means the token is wrong or the board is
on neither host: check it, and do not guess a different company. A 429 or a 5xx
means the board is busy or down: try again later.

## What the number means

"Names 6 of your skills" is lexical: the posting's text contains six of the
skills the profile lists. It is a filter for what is worth reading, not a fit
score, and it cannot see a skill the profile does not list. Say so. The fit
score comes after `jobhunt-posting` has read the one they choose.

## What this never does

- **Never applies.** It lists; the person reads and chooses.
- **Never touches LinkedIn**, and never scrapes: these are the boards' own
  public APIs.
- **Never widens the skills list** from the postings. What counts is what the
  profile says.
