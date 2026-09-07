"""The invention guard: what it catches, and what it must not flag."""

from job_hunter.generate.guard import Support, check, check_all
from job_hunter.profile.models import Profile, Severity


def support_for(profile):
    return Support.of(profile)


def test_text_drawn_from_the_profile_is_clean(profile):
    text = "Cut ETL runtime by 35% by rewriting the dbt models."
    assert check(text, support_for(profile), path="x") == []


def test_invented_tool_is_flagged(profile):
    issues = check("Led the migration to Kubernetes.", support_for(profile), path="x")
    assert len(issues) == 1
    assert "Kubernetes" in issues[0].message
    assert issues[0].severity is Severity.WARNING


def test_invented_figure_is_flagged(profile):
    issues = check("Managed a team of 12 engineers.", support_for(profile), path="x")
    assert any("12" in i.message for i in issues)


def test_figure_present_in_the_profile_is_not_flagged(profile):
    assert check("Cut runtime by 35%.", support_for(profile), path="x") == []


def test_sentence_initial_capital_is_not_a_proper_noun(profile):
    # "Built" and "Mentored" start sentences; neither is a claim about a tool.
    text = "Built pipelines in Python. Mentored analysts."
    assert check(text, support_for(profile), path="x") == []


def test_acronym_is_checked_even_when_it_starts_a_sentence(profile):
    issues = check("GDPR compliance was my remit.", support_for(profile), path="x")
    assert any("GDPR" in i.message for i in issues)


def test_supported_acronym_passes(profile):
    assert check("ETL work throughout.", support_for(profile), path="x") == []


def test_harmless_words_are_never_flagged():
    empty = Support.of(Profile())
    assert check("I did the work in May and on Monday.", empty, path="x") == []


def test_support_can_be_widened(profile, job):
    # A cover letter may name the company; the CV's bullets may not.
    text = "I would like to do this at Zeta."
    assert check(text, support_for(profile), path="x") != []
    assert check(text, support_for(profile) | Support.of(job.company), path="x") == []


def test_requirements_are_deliberately_not_support(profile, job):
    """The whole point: the job asking for Kafka must not license claiming it."""
    widened = support_for(profile) | Support.of(job.company, job.title, job.location)
    issues = check("I have used Kafka in production.", widened, path="x")
    assert any("Kafka" in i.message for i in issues)


def test_issue_messages_are_not_themselves_support(profile):
    """An Issue's text must never widen the vocabulary it is complaining about."""
    from job_hunter.profile.models import Issue

    noisy = Issue(path="x", severity=Severity.WARNING, message="Kubernetes is missing")
    support = Support.of(profile, [noisy])
    assert check("Ran Kubernetes.", support, path="x") != []


def test_check_all_walks_lists_and_paths(profile):
    issues = check_all({"bullets": ["Fine work with dbt.", "Ran Kubernetes."]},
                       support_for(profile))
    assert len(issues) == 1
    assert issues[0].path == "bullets[1]"


def test_empty_text_is_clean(profile):
    assert check("", support_for(profile), path="x") == []
    assert check("   ", support_for(profile), path="x") == []
