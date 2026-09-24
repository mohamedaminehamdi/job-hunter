"""The invention guard: what it catches, and what it must not flag."""

import pytest
from jobhunt import WARNING, Profile, Support, check, check_all


def support_for(profile):
    return Support.of(profile)


def test_text_drawn_from_the_profile_is_clean(profile):
    text = "Cut ETL runtime by 35% by rewriting the dbt models."
    assert check(text, support_for(profile), path="x") == []


def test_invented_tool_is_flagged(profile):
    issues = check("Led the migration to Kubernetes.", support_for(profile), path="x")
    assert len(issues) == 1
    assert "Kubernetes" in issues[0].message
    assert issues[0].severity == WARNING


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
    from jobhunt import Issue

    noisy = Issue(path="x", severity=WARNING, message="Kubernetes is missing")
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


# --- English and French are the languages this reads -----------------------

def test_an_accented_word_survives_whole():
    """Matching on A-Za-z cut 'expérience' into 'exp' and showed the fragment."""
    support = Support.of("J'ai déployé Kubernetes")
    found = check("J'ai déployé Ansible", support, path="p", language="fr")
    assert any("'Ansible'" in i.message for i in found)
    assert not any("ploy" in i.message for i in found)


def test_a_french_letter_against_a_french_profile_is_quiet():
    support = Support.of("J'ai déployé l'infrastructure Kubernetes chez Acme.")
    assert check("J'ai déployé l'infrastructure Kubernetes.", support,
                       path="p", language="fr") == []


def test_a_french_letter_still_catches_a_real_invention():
    support = Support.of("J'ai déployé Kubernetes chez Acme.")
    found = check("J'ai déployé Kubernetes et OpenStack chez Acme.", support,
                        path="p", language="fr")
    assert [i.message for i in found] and "OpenStack" in found[0].message


@pytest.mark.parametrize("written, profile_form", [
    ("25 000", "25,000"),      # French grouping against an English profile
    ("25.000", "25,000"),      # and the dotted form
    ("1 200", "1,200"),
])
def test_a_figure_is_the_same_figure_in_either_locale(written, profile_form):
    support = Support.of(f"A fleet of {profile_form} devices.")
    assert check(f"Une flotte de {written} appareils.", support,
                       path="p", language="fr") == []


def test_a_decimal_comma_is_a_decimal_not_a_thousand():
    support = Support.of("Latency of 1.8s.")
    assert check("Latence de 1,8s.", support, path="p", language="fr") == []


def test_a_language_it_cannot_read_says_so_once_instead_of_flagging_everything():
    """German capitalises every noun, so the proper-noun check reports the letter."""
    support = Support.of("I ran Kubernetes at Acme.")
    found = check(
        "Ich habe die Plattform für Produktionsgeräte mit Kubernetes betrieben.",
        support, path="paragraphs[0]", language="de")

    assert len(found) == 1
    assert "only reads English and French" in found[0].message


def test_figures_are_still_checked_in_a_language_it_cannot_read():
    support = Support.of("A fleet of 25,000 devices.")
    found = check("Eine Flotte von 99 Geräten.", support, path="p", language="de")
    assert any("99" in i.message for i in found)


def test_the_unreadable_language_notice_is_said_once_per_document():
    support = Support.of("I ran Kubernetes at Acme.")
    found = check_all({"paragraphs": ["Erster Absatz hier.", "Zweiter Absatz hier."]},
                            support, language="de")
    assert sum("only reads English and French" in i.message for i in found) == 1


def test_an_unknown_language_is_still_checked():
    """A posting whose language the parser could not name is usually English."""
    support = Support.of("I ran Kubernetes at Acme.")
    found = check("I ran OpenStack at Acme.", support, path="p", language="")
    assert any("OpenStack" in i.message for i in found)


def test_english_is_unchanged_by_any_of_this():
    support = Support.of("I ran Kubernetes at Acme, cutting cost by 40%.")
    assert check("Cut cost 40% running Kubernetes at Acme.", support,
                       path="p", language="en") == []


def test_an_english_summary_under_a_foreign_posting_is_still_checked():
    """The letter follows the posting's language; the CV summary does not."""
    support = Support.of("I ran Kubernetes at Acme for two years.")
    summary = ("DevOps engineer who has run Kubernetes and OpenStack in production "
               "at Acme, and who is comfortable with the whole delivery path.")
    found = check(summary, support, path="summary", language="de")
    assert any("OpenStack" in i.message for i in found)


def test_a_german_letter_under_a_german_posting_is_not_checked():
    support = Support.of("I ran Kubernetes at Acme for two years.")
    german = ("Ich habe die Plattform für unsere Produktionsgeräte mit Kubernetes "
              "betrieben und die Pipelines dafür aufgebaut.")
    found = check(german, support, path="paragraphs[0]", language="de")
    assert len(found) == 1 and "only reads English and French" in found[0].message


# --- `asked`: covered only by the deleted answers tests, so ported here -----
#
# These used to go through `answers.answer()` with a stubbed model. Calling
# `check()` directly is a better test of the same thing: it is the guard's
# behaviour being pinned, not the answer generator's.

def test_a_term_the_question_introduced_is_worded_for_a_question():
    """An honest no has to write the word, so "remove it" is wrong advice."""
    support = Support.of("I ran Kubernetes at Acme.")
    asked = Support.wording_of("Have you used Workday?")
    found = check("No. I have never used Workday.", support, path="answer", asked=asked)

    flagged = [i.message for i in found if "Workday" in i.message]
    assert flagged, "the term is still surfaced"
    assert "the question's own term" in flagged[0]
    assert "Remove it" not in flagged[0]


def test_wording_it_differently_is_not_excusing_it():
    support = Support.of("I ran Kubernetes at Acme.")
    asked = Support.wording_of("Have you used Workday?")
    found = check("Yes, I have used Workday for three years.", support,
                  path="answer", asked=asked)
    assert any("Workday" in i.message for i in found)



# --- naming a requirement in order to deny it -------------------------------

def test_a_letter_may_name_the_postings_words_without_them_becoming_support(profile, job):
    """A good letter says "I have not used Kafka" - the word cannot be avoided.

    Found end to end: the letter that was honest about not knowing SQL got told
    to delete "SQL", which would have turned a straight sentence into a vague
    one. The claim is still surfaced; only the advice changes.
    """
    from jobhunt import write_letter
    honest = write_letter(profile, job, {"paragraphs": [
        "I have not used Kafka, and would rather say so than imply otherwise."]})
    assert len(honest.issues) == 1
    assert "posting's own term" in honest.issues[0].message
    assert "check this does not claim it" in honest.issues[0].message


def test_the_posting_still_never_becomes_support(profile, job):
    """The dishonest version is flagged too. The guard is lexical - it cannot
    tell a denial from a boast, and it does not pretend to."""
    from jobhunt import write_letter
    claimed = write_letter(profile, job, {"paragraphs": [
        "I am deeply experienced in Kafka and have run it in production."]})
    assert [i.message for i in claimed.issues] != []


def test_a_word_the_posting_never_used_is_flatly_unsupported(profile, job):
    from jobhunt import write_letter
    invented = write_letter(profile, job, {"paragraphs": [
        "I led the OpenStack migration."]})
    assert "does not appear in your profile" in invented.issues[0].message
