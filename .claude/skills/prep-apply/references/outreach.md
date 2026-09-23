# Who to message, and what to say

Write `outreach.json`. You name the *roles* worth contacting; `skill outreach`
builds every LinkedIn URL, because a URL that comes out of a model is a URL that
can be wrong or hostile.

Nobody is contacted automatically. This produces searches to run and a message
to adapt.

## The four tiers, in the order that actually gets replies

1. **`alumni`** - somebody from their university now at that company. By a
   distance the highest chance of a reply, and the one most outreach advice
   misses. Give no title; the script builds the search from their education.
2. **`peer`** - the job title itself, seniority stripped. A future colleague
   replies. Someone two rungs up does not.
3. **`manager`** - the likely hiring manager. Derive it from the posting's own
   title: "Data Engineer" → "Data Engineering Manager", "Head of Data". Keep it
   to a title that plausibly exists at a company that size.
4. **`recruiter`** - "Technical Recruiter", "Talent Acquisition". Lowest value
   for a student, but real.

```json
{
  "targets": [
    {"tier": "alumni", "why": "Same university, now there"},
    {"tier": "peer", "title": "Data Engineer", "why": "Would be a colleague"},
    {"tier": "manager", "title": "Data Engineering Manager", "why": "Likely hiring"}
  ],
  "message": {"subject": "", "note": "", "inmail": ""}
}
```

## The message

Three fields: a `subject` (under 70 characters), a `note` for a connection
request (**under 280 characters - LinkedIn rejects longer, the script checks**),
and an `inmail` of at most 150 words.

Four things every version must do. Each is checked.

1. **Name one specific thing from the posting** that is not the job title - a
   system, a problem, a scale. "I saw you run dbt on Postgres" is specific;
   "I'm excited about the Data Engineer role" is what everyone sends.
2. **Name one specific thing they have done**, with its figure, from the
   profile. The message goes through the same invention guard as the letter.
3. **Ask one answerable question.** Not "would love to connect". Something the
   recipient can answer in two sentences from their own experience: how the
   team splits ownership, what the on-call rota is really like, what surprised
   them in their first month.
4. **Ask a question, do not ask for a referral.** This is the highest-leverage
   line here. A student asking a future colleague what the work is like gets
   replies. A stranger asking for a referral gets ignored, and burns the
   contact.

Write in the language of the posting.
