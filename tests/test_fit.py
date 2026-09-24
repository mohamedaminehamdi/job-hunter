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


def test_a_quantity_adjective_is_not_a_requirement(profile):
    """"Significant experience..." asks for experience, not for Significant."""
    wordy = jobhunt.clone(JOB, **{"requirements": [
        "Significant experience delivering large-scale infrastructure, HPC included"]})
    found = jobhunt.score(wordy, profile)
    assert "Significant" not in found.gaps
    assert "HPC" in found.gaps
