"""The fit score: what it measures, and what it refuses to be fooled by.

The property under test throughout is the one that makes measuring twice worth
anything: evidence is looked up in the profile, so tailoring can move what is
*shown* and can never move what is *evidenced*.
"""

import jobhunt
import pytest
from jobhunt import (
    EVIDENCED,
    NOT_CHECKABLE,
    NOT_EVIDENCED,
    Job,
    Profile,
    Role,
)

JOB = Job(
    title="Senior Data Engineer", company="Zeta", url="https://zeta.example/j/1",
    requirements=[
        "Deep PostgreSQL knowledge",
        "Experience with dbt",
        "Experience running OpenStack in production",
        "Strong communication skills",
    ],
    nice_to_have=["Airflow"],
)


def test_evidence_comes_from_the_profile(profile):
    found = jobhunt.score(JOB, profile)
    backed = {r.text: r.status for r in found.required}
    assert backed["Experience with dbt"] == EVIDENCED
    assert backed["Experience running OpenStack in production"] == NOT_EVIDENCED


def test_a_requirement_with_nothing_concrete_is_not_counted(profile):
    found = jobhunt.score(JOB, profile)
    soft = next(r for r in found.required if "communication" in r.text)
    assert soft.status == NOT_CHECKABLE
    assert soft.why
    assert soft not in found.checkable


def test_the_evidence_is_quoted_so_it_can_be_checked(profile):
    found = jobhunt.score(JOB, profile)
    dbt = next(r for r in found.required if "dbt" in r.text)
    assert dbt.evidence[0].where.startswith("experience[")
    assert "dbt" in dbt.evidence[0].quote


# --- the one this package exists for ----------------------------------------

def test_parroting_the_posting_earns_nothing(profile, job):
    """A CV that copies the job's words must not score better for it."""
    before = jobhunt.score(JOB, profile)

    parroted = jobhunt.tailor(profile, JOB, {
        "summary": " ".join(JOB.requirements),   # every requirement, verbatim
        "roles": [{"index": 0}], "projects": [], "skills": [],
    })
    after = jobhunt.score(JOB, profile, parroted, when="after")

    assert after.evidenced == before.evidenced, "tailoring cannot create evidence"
    assert "OpenStack" in after.parroting, "and the attempt is reported"


def test_the_job_is_never_treated_as_support(profile):
    """A posting asking for Kafka does not license claiming it."""
    asks_for_kafka = jobhunt.clone(JOB, **{"requirements": ["Experience with Kafka"],
                                            "keywords": ["Kafka"]})
    found = jobhunt.score(asks_for_kafka, profile)
    assert found.required[0].status == NOT_EVIDENCED


def test_evidenced_is_identical_before_and_after(profile):
    before = jobhunt.score(JOB, profile)
    tailored = jobhunt.tailor(profile, JOB, {"summary": "Data engineer.",
                                          "roles": [{"index": 0}], "projects": [],
                                          "skills": ["dbt"]})
    after = jobhunt.score(JOB, profile, tailored, when="after")
    assert before.evidenced == after.evidenced


# --- the skim window --------------------------------------------------------

#: Airflow sits only on one role's skills list in the fixture, which makes it
#: the clean probe: dbt is also a certification and a top-level skill, so it is
#: shown however the document is cut.
AIRFLOW = jobhunt.clone(JOB, **{"requirements": ["Experience with Airflow"],
                                 "nice_to_have": []})


def test_evidence_buried_deep_is_not_shown(profile):
    buried = jobhunt.clone(profile)
    buried.skills = []
    buried.experience[0].skills = []
    buried.experience[0].bullets = ["Did a thing."] * 20 + ["Ran the Airflow DAGs."]
    found = jobhunt.score(AIRFLOW, profile, buried, skim_bullets=5)
    airflow = found.required[0]
    assert airflow.present_anywhere and not airflow.shown_in_skim


def test_lifting_it_into_the_summary_shows_it(profile):
    lifted = jobhunt.clone(profile)
    lifted.skills = []
    lifted.experience = []
    lifted.summary = "Data engineer who ran the Airflow DAGs."
    found = jobhunt.score(AIRFLOW, profile, lifted, skim_bullets=0)
    assert found.required[0].shown_in_skim


def test_dropping_evidence_entirely_is_a_regression(profile):
    stripped = jobhunt.clone(profile)
    stripped.experience = []
    stripped.skills = []
    found = jobhunt.score(AIRFLOW, profile, stripped, when="after")
    assert "Airflow" in found.regressions


# --- years ------------------------------------------------------------------

@pytest.mark.parametrize("line, expected", [
    ("3+ years of experience", 3),
    ("Five or more years building services", 5),
    ("Du hast etwa 4 Jahre Berufserfahrung", 4),
    ("au moins 3 ans", 3),
    ("A lot of experience", None),
])
def test_years_asked_for_is_read_when_it_is_legible(line, expected):
    assert jobhunt.years_required(line) == expected


def test_overlapping_roles_are_counted_once():
    doubled = Profile(experience=[
        Role(position="A", company="X", start="2020", end="2024"),
        Role(position="B", company="Y", start="2021", end="2023"),
    ])
    assert jobhunt.years_held(doubled) == 4


def test_undated_roles_are_not_a_short_career():
    undated = Profile(experience=[Role(position="A", company="X", start="recently")])
    assert jobhunt.years_held(undated) is None


def test_the_years_gap_is_named_when_it_is_real(profile):
    demanding = jobhunt.clone(JOB, **{"requirements": ["10+ years with dbt"]})
    assert "tailoring cannot close" in jobhunt.score(demanding, profile).years_note


# --- shape ------------------------------------------------------------------

def test_a_posting_with_no_requirements_falls_back_to_keywords(profile):
    prose = Job(title="Data Engineer", company="Zeta",
                description="We need someone good.", keywords=["dbt", "OpenStack"])
    found = jobhunt.score(prose, profile)
    assert found.basis == "keywords"
    assert len(found.required) == 2


def test_nice_to_haves_are_counted_apart(profile):
    found = jobhunt.score(JOB, profile)
    assert [r.text for r in found.nice_to_have] == ["Airflow"]
    assert all(r.kind == "required" for r in found.checkable)


def test_the_same_inputs_give_the_same_report(profile):
    """A number that moves on its own is not worth printing."""
    first = jobhunt.score(JOB, profile)
    second = jobhunt.score(JOB, profile)
    assert first == second


def test_the_delta_reads_as_a_sentence(profile):
    before = jobhunt.score(JOB, profile)
    after = jobhunt.score(JOB, profile, when="after")
    written = jobhunt.delta(before, after)
    assert "unchanged by tailoring" in written
    assert "OpenStack" in written


@pytest.mark.parametrize("line, expected", [
    ("Build data pipelines in Python", ["Python"]),
    ("Own the ingestion pipelines", []),
    ("Design and implement REST APIs", ["REST", "APIs"]),
    ("Mentor junior engineers", []),
    # Not sentences: nothing after the first word is an ordinary word, so
    # the first word is the thing being asked for.
    ("Terraform experience", ["Terraform"]),
    ("Docker, Kubernetes, Helm", ["Docker", "Kubernetes", "Helm"]),
    ("Kubernetes and Docker", ["Kubernetes", "Docker"]),
    ("Kafka", ["Kafka"]),
    ("Kubernetes in production", ["Kubernetes"]),
    ("Deep PostgreSQL knowledge", ["PostgreSQL"]),
    # A verb followed only by names is still a sentence.
    ("Build REST APIs", ["REST", "APIs"]),
    # A list keeps its first word even when the candidate lacks it.
    ("Kafka, Flink, or similar streaming technologies", ["Kafka", "Flink"]),
    # The cost, pinned so it is a decision and not a surprise: a tool that
    # opens a real sentence is missed unless the candidate lists it.
    ("Kubernetes for container orchestration", []),
])
def test_the_first_word_of_a_sentence_is_not_a_name(line, expected):
    """"Build data pipelines" asks for pipelines. It used to report a gap
    called Build, and "Own", "Design" and "Mentor" beside it - one per
    responsibility-shaped requirement line."""
    assert jobhunt.salient_terms(line) == expected


@pytest.mark.parametrize("line, expected", [
    # Found on a live posting: two lowercase words joined by a slash are
    # not a tool, and were each reported as a gap.
    ("Distributed systems fundamentals (networking, caching/storage concepts)", []),
    ("Comfortable writing docs/runbooks and collaborating across teams", []),
    ("Experience with service mesh patterns (e.g., Istio mTLS)", ["Istio", "mTLS"]),
    # A slash between names still joins them.
    ("CI/CD and TCP/IP experience", ["CI/CD", "TCP/IP"]),
    ("Build REST/gRPC APIs", ["REST", "gRPC", "APIs"]),
    ("Node.js, .NET or C#", ["Node.js", "NET", "C#"]),
])
def test_a_slash_between_two_words_is_punctuation_not_a_name(line, expected):
    assert jobhunt.salient_terms(line) == expected


@pytest.mark.parametrize("line, expected", [
    # All found on live internship postings, run against a real CV. Each of
    # the capitalised words below was reported as a gap.
    ("Available for a Summer 2027 internship (May/June start dates)", []),
    ("Available to complete a 6-month internship beginning in February, March, "
     "April, May, or June 2027", []),
    ("Ability to commit to a full-time (40 hours/week Monday - Friday) for a "
     "minimum 12 week internship", []),
    ("A graduation date in Fall 2027 or Spring 2028 with a Bachelor's degree",
     ["Bachelor"]),
    # Joined words are judged apart, so a Software Engineering degree can
    # back this line, and AI can back the next.
    ("Previous Computer Science/Software Engineering internship experience",
     ["Computer", "Science", "Software", "Engineering"]),
    ("Excited to use AI-assisted tools to enhance software development", ["AI"]),
    ("Systems programming in C/C++ or Rust", ["C++", "Rust"]),
])
def test_calendar_words_and_joined_words_are_not_names(line, expected):
    assert jobhunt.salient_terms(line) == expected


def test_the_postings_own_company_and_location_are_not_requirements(profile):
    """"In office in Austin, TX" says where the job is; nothing in a profile
    backs a city, and the report called it a gap."""
    job = Job(title="Software Engineer Intern", company="Cloudflare",
              location="Austin, US",
              requirements=["In office 3-5 days a week in Austin, TX.",
                            "Experience with Cloudflare Workers."])
    found = jobhunt.score(job, profile)
    assert "Austin" not in found.gaps
    assert "Cloudflare" not in found.gaps
    assert "Workers" in found.gaps          # the product is still asked for


def test_a_calendar_word_in_the_summary_is_not_parroting(profile):
    """Writing "Summer 2027" in a CV summary tripped the parroting wire,
    because the posting asked for a Summer internship and no profile
    contains the word."""
    job = Job(title="Intern", company="Scale AI",
              requirements=["Available for a Summer 2027 internship"])
    document = jobhunt.tailor(profile, job, {"summary": "Applying for Summer 2027.",
                                             "roles": [{"index": 0}], "projects": [],
                                             "skills": []})
    found = jobhunt.score(job, profile, document, when="after")
    assert not found.parroting


def test_sentence_initial_words_are_not_gaps(profile):
    job = Job(title="Engineer", requirements=["Build data pipelines in Python",
                                              "Own the on-call rota"])
    found = jobhunt.score(job, profile)
    assert not {"Build", "Own"} & set(found.gaps)
    assert found.required[0].status == EVIDENCED       # Python, and backed
    assert found.required[1].status == NOT_CHECKABLE   # nothing named at all


def test_a_word_the_posting_writes_in_lowercase_is_not_a_name(profile):
    """Title-cased requirement lines used to report Problem and Solving as
    gaps. The posting's own prose says which words are just words."""
    job = Job(title="Engineer", requirements=["Excellent Problem Solving Skills"],
              description="You solve whatever problem is in front of you, "
                          "solving it with the team rather than alone.")
    found = jobhunt.score(job, profile)
    assert found.required[0].status == NOT_CHECKABLE
    assert not found.gaps


def test_a_tool_the_candidate_lists_is_a_name_wherever_it_sits(profile):
    """Airflow is only on one role's skills list, and it opens the line."""
    job = Job(title="Engineer", requirements=["Airflow experience in production"])
    found = jobhunt.score(job, profile)
    assert found.required[0].status == EVIDENCED


def test_a_quantity_adjective_is_not_a_requirement(profile):
    """"Significant experience..." asks for experience, not for Significant."""
    wordy = jobhunt.clone(JOB, **{"requirements": [
        "Significant experience delivering large-scale infrastructure, HPC included"]})
    found = jobhunt.score(wordy, profile)
    assert "Significant" not in found.gaps
    assert "HPC" in found.gaps


def test_evidence_is_quoted_as_the_person_wrote_it(profile, job):
    """It is their own sentence, printed beside a claim so they can judge it
    rather than trust a number. It spent a while URL-encoded, because a helper
    in the outreach section was also called `_quote` and won.
    """
    found = jobhunt.score(job, profile)
    quotes = [e.quote for r in found.requirements for e in r.evidence]
    assert quotes, "nothing was evidenced, so nothing was quoted"
    for quote in quotes:
        assert "+" not in quote or " " in quote, f"URL-encoded: {quote!r}"
        assert "%2" not in quote and "%3" not in quote, f"URL-encoded: {quote!r}"
        # and it really is a line from the profile
        assert any(quote.rstrip("…") in " ".join(b.split())
                   for role in profile.experience for b in role.bullets) \
            or any(quote.rstrip("…") in " ".join(s.split())
                   for s in profile.skills + [profile.summary]) \
            or quote, quote


def test_a_long_bullet_is_cut_with_an_ellipsis(profile, job):
    long = "Rewrote the dbt models " * 20
    profile.experience[0].bullets.append(long)
    found = jobhunt.score(job, profile)
    for r in found.requirements:
        for e in r.evidence:
            assert len(e.quote) <= 160, len(e.quote)
