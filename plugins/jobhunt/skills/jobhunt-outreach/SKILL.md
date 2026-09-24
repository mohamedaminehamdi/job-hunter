---
name: jobhunt-outreach
description: >
  Work out who at a company is worth messaging about a role, build the LinkedIn
  searches that find them, and draft a message that earns a reply. Use when
  someone asks who to contact about a job.
allowed-tools: Bash, Read, Write
---

# Who to message

It does **not** scrape LinkedIn. LinkedIn walls and throttles automated access
and the risk of working around that lands on the user's account, not on this
repo. It does the part it can do honestly: work out who is worth contacting,
build the search, draft what to say. They run the search and press send.

You name job titles. **Every URL is built by the script**, so a malformed or
hostile link cannot come out of your JSON.

```json
{
  "targets": [
    {"tier": "alumni", "why": "Same university, now there."},
    {"tier": "peer", "title": "Data Engineer", "why": "Would be their colleague."},
    {"tier": "manager", "title": "Head of Data", "why": "Likely owns this req."}
  ],
  "message": {
    "subject": "dbt at Acme",
    "note": "Under 280 characters. LinkedIn rejects longer.",
    "inmail": "Under 150 words."
  }
}
```

```bash
python3 outreach.py plan.json --run <run>
```

Tiers, in order of how likely a reply is: `alumni`, `peer`, `manager`,
`recruiter`. Alumni needs no title - it is built from their own education.

## The message

**Ask a question you actually want answered.** A student asking a future
colleague what the on-call rota is really like gets a reply. Asking a stranger
for a referral does not.

- One concrete thing from their profile, with the figure.
- One specific question about how the team works.
- No "I would love to connect". No "I am passionate about".
- The connection note is 280 characters, hard. Over it, LinkedIn simply
  rejects the message when it is pasted.

## Exit 2

Over a platform limit. Shorten and try once more.

## Say this to the user

Nobody is contacted for them. `outreach.md` holds the searches to run and a
message to adapt - the sending is theirs.
