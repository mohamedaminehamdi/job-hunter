"""Tailoring: the boundary CONTRIBUTING asks to be pinned by a test.

A generator may select, reorder and reword facts from the profile. It may not add
an employer, a date, a course, a tool or a metric. Most of that is structural
here - the model answers with indices - so these tests pin the structure as much
as the prompt.
"""

import json

import pytest

from job_hunter.generate import cv
from job_hunter.generate.cv import TailorError
from job_hunter.profile.models import Profile, Severity

REPLY = {
    "summary": "Data engineer with production pipeline experience.",
    "roles": [{"index": 0, "bullets": ["Cut ETL runtime by 35% by rewriting the dbt models."]},
              {"index": 1, "bullets": ["Built the finance dashboards used by 40 people."]}],
    "projects": [0],
    "skills": ["Python", "dbt", "SQL"],
}


# --- the invention boundary ----------------------------------------------

def test_a_job_requirement_does_not_become_a_skill(profile, job, stub_llm):
    """Kafka is in the job's nice-to-haves and not in the profile. It must not appear."""
    stub_llm(json.dumps({**REPLY, "skills": ["Python", "Kafka", "Terraform"]}))
    document = cv.tailor(profile, job)

    assert "Kafka" not in document.skills
    assert "Terraform" not in document.skills
    assert document.skills == ["Python"]
    dropped = [i for i in document.issues if i.path == "skills"]
    assert dropped and "Kafka" in dropped[0].message


def test_an_invented_employer_cannot_be_expressed(profile, job, stub_llm):
    """The model has no way to name a company: it answers with indices."""
    stub_llm(json.dumps({**REPLY, "roles": [
        {"index": 0, "company": "Google", "position": "Staff Engineer",
         "start": "2015", "bullets": ["Did something."]}]}))
    document = cv.tailor(profile, job)

    companies = [role.company for role in document.experience]
    assert companies == ["Acme"]
    assert document.experience[0].position == "Data Engineer"
    assert document.experience[0].start == "2021"  # the profile's date, not the model's


def test_invented_bullet_text_is_flagged_not_silently_kept(profile, job, stub_llm):
    stub_llm(json.dumps({**REPLY, "roles": [
        {"index": 0, "bullets": ["Scaled the cluster to 400 nodes with Kubernetes."]}]}))
    document = cv.tailor(profile, job)

    messages = " ".join(i.message for i in document.issues)
    assert "Kubernetes" in messages
    assert "400" in messages
    assert all(i.severity is Severity.WARNING for i in document.issues)


def test_education_is_copied_and_never_generated(profile, job, stub_llm):
    stub_llm(json.dumps({**REPLY, "education": [
        {"level": "PhD", "institution": "MIT", "courses": ["Rocket Science"]}]}))
    document = cv.tailor(profile, job)

    assert [e.institution for e in document.education] == ["TU Berlin"]
    assert document.education[0].level == "MSc"
    assert document.certifications == profile.certifications
    assert document.languages == profile.languages
    assert document.personal == profile.personal


def test_the_prompt_states_the_rules(profile, job, stub_llm):
    calls = stub_llm(json.dumps(REPLY))
    cv.tailor(profile, job)

    assert "never add" in calls["system"].lower()
    assert "Do not add employers" in calls["system"]
    assert "Never restate a requirement" in calls["system"]
    # Both halves reach the model, and the roles are numbered for it.
    assert "[0] Data Engineer - Acme" in calls["prompt"]
    assert "Senior Data Engineer" in calls["prompt"]


# --- assembly ------------------------------------------------------------

def test_roles_keep_the_profile_order_not_the_model_s(profile, job):
    """Ranked by relevance, a past role lands above the current one."""
    document = cv.assemble(profile, job, {**REPLY, "roles": [{"index": 1}, {"index": 0}]})
    assert [r.company for r in document.experience] == ["Acme", "Beta"]


def test_the_model_still_chooses_which_roles_appear(profile, job):
    document = cv.assemble(profile, job, {**REPLY, "roles": [{"index": 1}]})
    assert [r.company for r in document.experience] == ["Beta"]


def test_a_dropped_role_is_reported(profile, job):
    document = cv.assemble(profile, job, {**REPLY, "roles": [{"index": 0}]})
    left_out = [i for i in document.all_issues if "Left off" in i.message]
    assert left_out and "Beta" in left_out[0].message


def test_nothing_is_reported_when_every_role_is_kept(profile, job):
    document = cv.assemble(profile, job, {**REPLY, "roles": [{"index": 0}, {"index": 1}]})
    assert not any("Left off" in i.message for i in document.all_issues)


def test_a_role_with_no_bullets_falls_back_to_the_profile(profile, job):
    document = cv.assemble(profile, job, {**REPLY, "roles": [{"index": 0, "bullets": []}]})
    assert document.experience[0].bullets == profile.experience[0].bullets


def test_out_of_range_and_duplicate_indices_are_dropped(profile, job):
    document = cv.assemble(profile, job, {**REPLY, "roles": [
        {"index": 0}, {"index": 0}, {"index": 99}, {"index": -1}, {"index": "x"}]})
    assert [r.company for r in document.experience] == ["Acme"]


def test_index_accepted_in_the_shapes_models_use(profile, job):
    for entry in (1, "1", {"index": 1}, {"i": 1}, {"index": "1"}):
        document = cv.assemble(profile, job, {**REPLY, "roles": [entry]})
        assert [r.company for r in document.experience] == ["Beta"], entry


def test_no_roles_selected_keeps_them_all_and_says_so(profile, job):
    document = cv.assemble(profile, job, {**REPLY, "roles": []})
    assert len(document.experience) == len(profile.experience)
    assert any("did not select" in i.message for i in document.issues)


def test_bullets_are_capped(profile, job):
    many = [f"Did thing number {i} at work." for i in range(20)]
    document = cv.assemble(profile, job, {**REPLY, "roles": [{"index": 0, "bullets": many}]})
    assert len(document.experience[0].bullets) == cv.MAX_BULLETS


def test_bullet_characters_are_stripped(profile, job):
    document = cv.assemble(profile, job, {**REPLY, "roles": [
        {"index": 0, "bullets": ["- Mentored two junior analysts.", "  ", "• Cut runtime."]}]})
    assert document.experience[0].bullets == ["Mentored two junior analysts.", "Cut runtime."]


def test_skills_fall_back_to_the_profile_when_none_survive(profile, job):
    document = cv.assemble(profile, job, {**REPLY, "skills": ["Kafka"]})
    assert document.skills == profile.skills


def test_skills_may_come_from_a_role_or_a_project(profile, job):
    """Airflow is only listed on a role; Python only on a project. Both are real."""
    document = cv.assemble(profile, job, {**REPLY, "skills": ["Airflow", "Python"]})
    assert document.skills == ["Airflow", "Python"]


def test_summary_falls_back_to_the_profile(profile, job):
    document = cv.assemble(profile, job, {**REPLY, "summary": ""})
    assert document.summary == profile.summary


def test_projects_are_selected_not_reworded(profile, job):
    document = cv.assemble(profile, job, {**REPLY, "projects": [{"index": 0,
                                                                 "description": "Rewritten!"}]})
    assert document.projects == [profile.projects[0]]


def test_the_document_carries_the_job_it_was_made_for(profile, job):
    document = cv.assemble(profile, job, REPLY)
    assert document.job_label == "Senior Data Engineer at Zeta"
    assert document.job_slug == "zeta-senior-data-engineer"


def test_placeholder_text_blocks_the_document(profile, job):
    document = cv.assemble(profile, job, {**REPLY, "summary": "Engineer at [Company]."})
    assert document.blocking
    assert not document.is_renderable


def test_issue_text_does_not_itself_become_a_blocking_issue(profile, job):
    """A warning mentioning '[Company]' must not be read as placeholder content."""
    document = cv.assemble(profile, job, {**REPLY, "roles": [
        {"index": 0, "bullets": ["Ran Kubernetes."]}]})
    assert document.issues  # the guard fired
    assert not document.blocking  # but that is not a blocker


# --- refusals ------------------------------------------------------------

def test_empty_profile_refused(job, stub_llm):
    stub_llm(json.dumps(REPLY))
    with pytest.raises(TailorError, match="nothing to tailor"):
        cv.tailor(Profile(), job)


def test_thin_job_refused(profile, stub_llm):
    from job_hunter.jobs.models import Job

    stub_llm(json.dumps(REPLY))
    with pytest.raises(TailorError, match="no description"):
        cv.tailor(profile, Job(title="Data Engineer"))


def test_unreadable_reply_refused(profile, job, stub_llm):
    stub_llm("I'm sorry, I can't help with that.")
    with pytest.raises(TailorError, match="did not return JSON"):
        cv.tailor(profile, job)


def test_fenced_reply_is_fine(profile, job, stub_llm):
    stub_llm(f"```json\n{json.dumps(REPLY)}\n```")
    assert cv.tailor(profile, job).summary == REPLY["summary"]
