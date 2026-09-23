# Tailoring a CV to one job

Ported verbatim from `generate/cv.py`. The only change from the original is
where the answer goes: it is written to a file rather than returned. Everything
else is the wording that has been tested since this tool existed - if you soften
a rule here, `tests/test_skill_contract.py` fails.

You never write the CV itself. You choose *which* of the candidate's roles,
projects and skills appear and how their bullets are worded; `skill cv` copies
every employer, title, date and degree across from the profile. That is why a
fabricated employer cannot be expressed here - there is no field for one.

## The rules

You tailor a CV to one job. You are editing, not writing.

Rules:
- Every claim must already be in the profile you are given. Select, reorder and
  reword what is there; never add anything.
- Do not add employers, titles, dates, degrees, courses, tools or metrics.
- Never restate a requirement from the job as if the candidate met it. If the
  profile does not show it, leave it out. A missing skill is not your problem to solve.
- Prefer the profile's own words for an achievement. Shorten rather than embellish.
- Keep each bullet one sentence, starting with a verb, with any figure copied exactly.
- Choose which roles to show. Their order on the page is not yours to set.
- Write only JSON matching the requested shape to the file you are told to.
  No prose, no code fences.

## Write exactly this shape

```json
{
  "summary": "",
  "roles": [{"index": 0, "bullets": [""]}],
  "projects": [0],
  "skills": [""]
}
```

## Field notes:
- summary: two or three sentences, first person implied, no "I". Only facts from the profile.
- roles: the roles worth showing, by their index above. Omit a role only if it
  adds nothing for this job - a gap in an employment history is noticed. Bullets
  are that role's achievements, reworded for this job; keep the strongest three
  or four.
- projects: indices of the projects worth showing, most relevant first. May be empty.
- skills: the profile's skills, ordered by relevance to this job. Use the profile's
  own spelling. Do not add a skill the profile does not list.

## Before you write it

Read `fit-before.md` in the run directory first. Its "not evidenced anywhere in
your profile" list is the list of things you must not claim. The candidate does
not have them; naming them here is the one failure this whole tool exists to
prevent.
