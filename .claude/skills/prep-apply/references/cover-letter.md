# Writing the cover letter

Ported verbatim from `generate/cover_letter.py`, with the same single change:
the answer is written to a file. `skill letter` supplies the candidate's name,
contact details and the date - you write only the greeting, the paragraphs and
the closing.

## The rules

You write a cover letter from a candidate's profile and one job posting.

Rules:
- Every claim about the candidate must already be in the profile. Never add one.
- Never claim a requirement the profile does not support, and never apologise for
  one it lacks. Write about what is there.
- No flattery about the company, no "I am thrilled", no restating the job advert.
- Say what the candidate has done that bears on this job, concretely, using the
  profile's own figures where it has them.
- Three short paragraphs at most. Plain, direct, first person.
- Write in the language of the posting.
- Never write a placeholder. If you do not know a name, address the team.
- Write only JSON matching the requested shape to the file you are told to.
  No prose, no code fences.

## Write exactly this shape

```json
{
  "greeting": "",
  "paragraphs": ["", ""],
  "closing": ""
}
```

## Field notes:
- greeting: e.g. "Dear Hiring Team," - a real greeting, never a bracketed placeholder.
- paragraphs: two or three. First: what the candidate does and why this role. Then:
  the specific evidence. Last (optional): a plain closing sentence.
- closing: e.g. "Kind regards," - the name is added afterwards, do not write it.

## Before you write it

The letter is the most tempting place to overclaim, because it is prose. Every
figure and proper noun you write is checked against the profile afterwards and
reported to the candidate. Writing in the posting's language is not optional -
a German posting gets a German letter.
