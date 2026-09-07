"""Cover letters and application answers: the same honesty rule, softer targets."""

import json

import pytest

from job_hunter.generate import answers as answers_mod
from job_hunter.generate import cover_letter
from job_hunter.generate.answers import AnswerError
from job_hunter.generate.cover_letter import LetterError
from job_hunter.profile.models import Profile, Severity

REPLY = {
    "greeting": "Dear Hiring Team,",
    "paragraphs": ["I build data pipelines and would like to do that at Zeta.",
                   "At Acme I cut ETL runtime by 35% by rewriting the dbt models."],
    "closing": "Kind regards,",
}


# --- cover letter --------------------------------------------------------

def test_contact_details_are_copied_not_written(profile, job, stub_llm):
    stub_llm(json.dumps({**REPLY, "personal": {"name": "Someone", "email": "x@y.z"}}))
    letter = cover_letter.write(profile, job)

    assert letter.personal == profile.personal
    assert letter.signature == "Ada Lovelace"
    assert letter.company == "Zeta"
    assert letter.role == "Senior Data Engineer"


def test_naming_the_company_is_allowed(profile, job):
    letter = cover_letter.assemble(profile, job, REPLY)
    assert letter.issues == []


def test_claiming_a_requirement_the_profile_lacks_is_flagged(profile, job):
    letter = cover_letter.assemble(profile, job, {**REPLY, "paragraphs": [
        "I have five years of Kafka and Terraform in production."]})
    messages = " ".join(i.message for i in letter.issues)
    assert "Kafka" in messages and "Terraform" in messages


def test_greeting_is_not_guarded_but_placeholders_still_block(profile, job):
    """'Dear Hiring Team,' is a salutation, not a claim - it must not warn."""
    fine = cover_letter.assemble(profile, job, REPLY)
    assert not any("Hiring" in i.message for i in fine.all_issues)

    broken = cover_letter.assemble(profile, job, {**REPLY, "greeting": "Dear [Hiring Manager],"})
    assert broken.blocking
    assert "placeholder" in broken.blocking[0].message.lower()


def test_a_letter_with_no_body_is_blocked(profile, job):
    letter = cover_letter.assemble(profile, job, {**REPLY, "paragraphs": []})
    assert any("no body text" in i.message for i in letter.blocking)


def test_defaults_fill_in_a_missing_greeting_or_closing(profile, job):
    letter = cover_letter.assemble(profile, job, {"paragraphs": ["Short and plain."]})
    assert letter.greeting == "Dear Hiring Team,"
    assert letter.closing == "Kind regards,"


def test_paragraphs_accept_one_blob(profile, job):
    letter = cover_letter.assemble(profile, job, {**REPLY, "paragraphs": "One.\n\nTwo."})
    assert letter.paragraphs == ["One.", "Two."]


def test_letters_are_capped(profile, job):
    letter = cover_letter.assemble(profile, job, {
        **REPLY, "paragraphs": [f"Paragraph {i} is here." for i in range(9)]})
    assert len(letter.paragraphs) == cover_letter.MAX_PARAGRAPHS


def test_body_reads_as_a_letter(profile, job):
    body = cover_letter.assemble(profile, job, REPLY).body
    assert body.startswith("Dear Hiring Team,")
    assert body.endswith("Ada Lovelace")


def test_the_prompt_forbids_flattery_and_placeholders(profile, job, stub_llm):
    calls = stub_llm(json.dumps(REPLY))
    cover_letter.write(profile, job)
    assert "No flattery" in calls["system"]
    assert "Never write a placeholder" in calls["system"]
    assert "language of the posting" in calls["system"]


def test_a_letter_needs_a_name(job, stub_llm):
    stub_llm(json.dumps(REPLY))
    with pytest.raises(LetterError, match="Add your name"):
        cover_letter.write(Profile(), job)


# --- answers -------------------------------------------------------------

def test_an_honest_no_is_kept_and_surfaced(profile, job, stub_llm):
    stub_llm(json.dumps({
        "answer": "No. I have not used Terraform.",
        "unsupported": "The profile shows no Terraform experience.",
    }))
    drafted = answers_mod.answer(profile, job, "Do you have Terraform experience?")

    assert drafted.text.startswith("No.")
    assert drafted.caveat
    assert any(i.severity is Severity.WARNING and "flagged a gap" in i.message
               for i in drafted.all_issues)


def test_an_invented_answer_is_flagged(profile, job, stub_llm):
    stub_llm(json.dumps({"answer": "Yes, I ran Terraform across 30 clusters.", "unsupported": ""}))
    drafted = answers_mod.answer(profile, job, "Terraform?")
    messages = " ".join(i.message for i in drafted.all_issues)
    assert "Terraform" in messages and "30" in messages


def test_word_limit_reaches_the_prompt(profile, job, stub_llm):
    calls = stub_llm(json.dumps({"answer": "Short.", "unsupported": ""}))
    answers_mod.answer(profile, job, "Why us?", words=40)
    assert "at most 40 words" in calls["prompt"]
    assert "An honest" in calls["system"]  # the rule that makes "no" an allowed answer


def test_an_empty_answer_is_blocking(profile, job, stub_llm):
    stub_llm(json.dumps({"answer": "", "unsupported": ""}))
    drafted = answers_mod.answer(profile, job, "Why us?")
    assert any(i.severity is Severity.BLOCKING for i in drafted.all_issues)


def test_no_question_no_call(profile, job, stub_llm):
    stub_llm("{}")
    with pytest.raises(AnswerError, match="No question"):
        answers_mod.answer(profile, job, "   ")


def test_word_count(profile, job, stub_llm):
    stub_llm(json.dumps({"answer": "One two three four.", "unsupported": ""}))
    assert answers_mod.answer(profile, job, "Q?").word_count == 4
