"""Application tracking: the states, the dates, and what must survive.

An application record is the only thing in this tool that no command can
rebuild, so most of these tests are about it surviving something - a re-search,
a cleared queue, a deleted job.
"""

from datetime import UTC, datetime, timedelta

import pytest

from job_hunter.apply import models as apply_models
from job_hunter.apply import store as apply_store
from job_hunter.apply.models import APPLIED, INTERVIEWING, OFFER, REJECTED, WITHDRAWN
from job_hunter.discover import store as queue_store
from job_hunter.discover.models import Candidate, Listing, Match
from job_hunter.jobs import store as job_store


def days_ago(n: int) -> str:
    return (datetime.now(UTC).date() - timedelta(days=n)).isoformat()


# --- an application starts when you say it did ------------------------------

def test_an_application_starts_the_day_it_was_sent(home, job):
    application = apply_store.record(job, home=home)
    assert application.status == APPLIED
    assert application.applied_on == apply_models.today()
    assert [e.status for e in application.history] == [APPLIED]


def test_the_date_you_give_it_is_the_date_it_keeps(home, job):
    application = apply_store.record(job, on=days_ago(30), home=home)
    assert application.applied_on == days_ago(30)
    assert application.days_quiet == 30


def test_it_copies_the_job_so_the_record_outlives_the_posting(home, job):
    application = apply_store.record(job, home=home)
    assert application.company == job.company
    assert application.role == job.title
    assert application.url == job.url


def test_an_unreadable_date_is_never_treated_as_an_old_one(home, job):
    apply_store.record(job, on="last tuesday", home=home)
    application = apply_store.load(job.slug, home)
    assert application.days_quiet is None
    assert not application.is_quiet()
    assert apply_store.outstanding(home) == []


def test_a_hand_edited_unquoted_date_still_loads(home, job):
    apply_store.record(job, home=home)
    path = apply_store.application_path(job.slug, home)
    path.write_text(path.read_text().replace(
        f"applied_on: '{apply_models.today()}'", "applied_on: 2026-08-24"))
    assert apply_store.load(job.slug, home).applied_on == "2026-08-24"


# --- states -----------------------------------------------------------------

def test_the_moves_a_state_allows_are_the_ones_it_offers(home, job):
    apply_store.record(job, home=home)
    assert INTERVIEWING in apply_store.load(job.slug, home).next_states
    apply_store.mark(job.slug, REJECTED, home=home)
    assert apply_store.load(job.slug, home).next_states == ()


def test_a_rejected_application_does_not_go_back_to_applied(home, job):
    apply_store.record(job, home=home)
    apply_store.mark(job.slug, REJECTED, home=home)

    assert apply_store.mark(job.slug, APPLIED, home=home) is None
    assert apply_store.load(job.slug, home).status == REJECTED


def test_an_unknown_state_changes_nothing(home, job):
    apply_store.record(job, home=home)
    assert apply_store.mark(job.slug, "ghosted", home=home) is None
    assert apply_store.load(job.slug, home).status == APPLIED


def test_marking_something_that_was_never_applied_to_does_nothing(home):
    assert apply_store.mark("no-such-job", REJECTED, home=home) is None


def test_every_move_is_kept_in_the_history(home, job):
    apply_store.record(job, home=home)
    apply_store.mark(job.slug, INTERVIEWING, home=home)
    apply_store.mark(job.slug, OFFER, home=home)

    history = apply_store.load(job.slug, home).history
    assert [e.status for e in history] == [APPLIED, INTERVIEWING, OFFER]


def test_an_offer_can_still_be_lost(home, job):
    apply_store.record(job, home=home)
    apply_store.mark(job.slug, OFFER, home=home)
    assert apply_store.mark(job.slug, WITHDRAWN, home=home).status == WITHDRAWN


# --- the store --------------------------------------------------------------

def test_an_application_round_trips(home, job):
    apply_store.record(job, channel="company form", sent=["cv", "letter"],
                       contact="Nadia", home=home)
    loaded = apply_store.load(job.slug, home)
    assert loaded.channel == "company form"
    assert loaded.sent == ["cv", "letter"]
    assert loaded.contact == "Nadia"


def test_a_corrupt_application_reads_as_missing_without_losing_the_others(home, job):
    apply_store.record(job, home=home)
    other = job.model_copy(update={"company": "Other", "title": "Platform Engineer"})
    apply_store.record(other, home=home)
    apply_store.application_path(job.slug, home).write_text("{[ not yaml")

    assert apply_store.load(job.slug, home) is None
    assert [a.company for a in apply_store.all_applications(home)] == ["Other"]


def test_recording_the_same_job_twice_does_not_reset_its_state(home, job):
    apply_store.record(job, channel="email", home=home)
    apply_store.mark(job.slug, INTERVIEWING, home=home)
    apply_store.record(job, channel="company form", home=home)

    again = apply_store.load(job.slug, home)
    assert again.status == INTERVIEWING
    assert again.channel == "company form"


def test_applications_are_listed_newest_first(home, job):
    apply_store.record(job, on=days_ago(30), home=home)
    recent = job.model_copy(update={"company": "Recent", "title": "Platform Engineer"})
    apply_store.record(recent, on=days_ago(1), home=home)
    assert [a.company for a in apply_store.all_applications(home)][0] == "Recent"


def test_counts_are_what_the_dashboard_shows(home, job):
    apply_store.record(job, home=home)
    other = job.model_copy(update={"company": "Other", "title": "Platform Engineer"})
    apply_store.record(other, on=days_ago(40), home=home)
    apply_store.mark(other.slug, REJECTED, home=home)

    tally = apply_store.counts(home)
    assert tally["total"] == 2 and tally["open"] == 1 and tally[REJECTED] == 1


# --- the four cases this feature exists for ---------------------------------

def test_a_job_added_by_hand_can_be_applied_to(home, job):
    """It never passed through the queue, so it has no candidate to hold a state."""
    job_store.save(job, home)
    apply_store.record(job, home=home)

    assert queue_store.load(home) == []
    assert apply_store.load(job.slug, home) is not None


def test_clearing_the_queue_leaves_the_applications_alone(home, job):
    queue_store.save([Candidate(listing=Listing(url="https://x.com/1"),
                                match=Match(score=70))], home)
    apply_store.record(job, home=home)

    queue_store.clear(home)
    assert queue_store.load(home) == []
    assert apply_store.load(job.slug, home) is not None


def test_a_later_search_does_not_touch_an_application(home, job):
    listing = Listing(url="https://x.com/1", title=job.title, company=job.company)
    queue_store.save([Candidate(listing=listing, match=Match(score=60))], home)
    apply_store.record(job, home=home)
    apply_store.mark(job.slug, INTERVIEWING, home=home)

    queue_store.merge(queue_store.load(home),
                      [Candidate(listing=listing, match=Match(score=95))])
    still = apply_store.load(job.slug, home)
    assert still.status == INTERVIEWING
    assert [e.status for e in still.history] == [APPLIED, INTERVIEWING]


def test_deleting_the_job_keeps_the_record_of_having_applied(home, job):
    job_store.save(job, home)
    apply_store.record(job, home=home)
    job_store.delete(job.slug, home)

    assert job_store.load(job.slug, home) is None
    assert apply_store.all_applications(home)[0].company == job.company


# --- follow-up --------------------------------------------------------------

def test_an_application_is_quiet_from_the_last_thing_that_happened(home, job):
    apply_store.record(job, on=days_ago(30), home=home)
    apply_store.add_note(job.slug, "chased the recruiter", home=home)
    assert apply_store.load(job.slug, home).days_quiet == 0


def test_chasing_them_takes_it_off_the_outstanding_list(home, job):
    apply_store.record(job, on=days_ago(30), home=home)
    assert apply_store.outstanding(home)

    apply_store.add_note(job.slug, "chased them", home=home)
    assert apply_store.outstanding(home) == []


def test_a_closed_application_is_never_outstanding(home, job):
    apply_store.record(job, on=days_ago(90), home=home)
    apply_store.mark(job.slug, REJECTED, on=days_ago(80), home=home)
    assert apply_store.outstanding(home) == []


def test_outstanding_is_the_longest_wait_first(home, job):
    apply_store.record(job, on=days_ago(20), home=home)
    older = job.model_copy(update={"company": "Older", "title": "Platform Engineer"})
    apply_store.record(older, on=days_ago(60), home=home)
    assert [a.company for a in apply_store.outstanding(home)][0] == "Older"


@pytest.mark.parametrize("age, quiet", [(13, False), (14, True), (40, True)])
def test_two_weeks_is_the_line(home, job, age, quiet):
    apply_store.record(job, on=days_ago(age), home=home)
    assert apply_store.load(job.slug, home).is_quiet() is quiet


def test_an_empty_note_is_not_an_event(home, job):
    apply_store.record(job, home=home)
    assert apply_store.add_note(job.slug, "   ", home=home) is None
    assert len(apply_store.load(job.slug, home).history) == 1
