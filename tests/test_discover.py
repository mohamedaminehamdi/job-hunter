"""Discovery: identity, scoring, the queue's memory, and one dead source.

No network and no browser here. The adapters are tested against payloads they
would really receive; what reaches out is stubbed, because what is under test is
the parsing and the plumbing, not httpx.
"""

import pytest

from job_hunter import discover
from job_hunter.discover import criteria as criteria_mod
from job_hunter.discover import match as match_mod
from job_hunter.discover import sources
from job_hunter.discover import store as queue_store
from job_hunter.discover.criteria import Criteria
from job_hunter.discover.models import Candidate, Listing, Match, canonical_url
from job_hunter.discover.sources import ats, indeed, linkedin, page
from job_hunter.discover.sources.browser import BrowserError

CRITERIA = Criteria(titles=["Backend Engineer"], locations=["Zurich"], greenhouse=["acme"])


def listing(**kwargs) -> Listing:
    return Listing(**{"url": "https://boards.example.com/jobs/1",
                      "title": "Backend Engineer", "company": "Acme",
                      "location": "Zurich, Switzerland", "source": "greenhouse", **kwargs})


# --- identity: the same job from three sources is one job -------------------

@pytest.mark.parametrize("url, expected", [
    ("https://x.com/jobs/1?utm_source=news&gh_src=abc", "https://x.com/jobs/1"),
    ("https://X.com/jobs/1/", "https://x.com/jobs/1"),
    ("https://x.com/jobs/1#apply", "https://x.com/jobs/1"),
    ("https://x.com/jobs/1?b=2&a=1", "https://x.com/jobs/1?a=1&b=2"),
])
def test_tracking_does_not_change_a_job_s_identity(url, expected):
    assert canonical_url(url) == expected


def test_the_same_posting_gets_one_id_from_two_sources():
    from_board = listing(url="https://x.com/jobs/1", source="greenhouse")
    from_search = listing(url="https://x.com/jobs/1?utm_campaign=feed", source="linkedin")
    assert from_board.id == from_search.id


def test_different_postings_never_collide():
    assert listing(url="https://x.com/jobs/1").id != listing(url="https://x.com/jobs/2").id


def test_an_id_is_readable_before_it_is_unique():
    assert listing().id.startswith("acme-backend-engineer-")


# --- criteria ---------------------------------------------------------------

def test_an_empty_search_says_what_it_needs():
    messages = " ".join(i.message for i in Criteria().report())
    assert "title" in messages and "source" in messages
    assert not Criteria().is_searchable


def test_a_criteria_with_a_board_and_a_title_is_searchable():
    assert CRITERIA.is_searchable
    assert CRITERIA.sources_enabled == ["greenhouse"]


def test_criteria_round_trips_through_yaml(home):
    criteria_mod.save(CRITERIA, home)
    assert criteria_mod.load(home) == CRITERIA


def test_broken_criteria_yaml_reads_as_empty_not_a_crash(home):
    criteria_mod.criteria_path(home).write_text("titles: [unclosed")
    assert criteria_mod.load(home).titles == []


def test_one_bad_field_does_not_lose_the_others():
    salvaged = criteria_mod.from_dict({"titles": ["Backend Engineer"], "min_score": "loads"})
    assert salvaged.titles == ["Backend Engineer"]


def test_workplace_preferences_only_rule_out_what_is_stated():
    remote_only = Criteria(hybrid=False, onsite=False)
    assert remote_only.wants_workplace("Remote")
    assert not remote_only.wants_workplace("On-site")
    assert remote_only.wants_workplace("")  # unstated is not a reason to skip it


# --- matching ---------------------------------------------------------------

def test_a_matching_title_and_location_scores_well(profile):
    result = match_mod.score(listing(title="Backend Engineer"), profile, CRITERIA)
    assert result.score >= 60
    assert any("Title matches" in r for r in result.reasons)


def test_a_shared_generic_word_is_not_a_title_match(profile):
    """'AI Engineer' and 'Backend Engineer' have only 'engineer' in common."""
    result = match_mod.score(listing(title="AI Engineer, GTM"), profile, CRITERIA)
    assert not any("Title" in r for r in result.reasons)


def test_the_skills_it_names_are_the_ones_it_reports(profile):
    hit = listing(title="Backend Engineer", snippet="You will write Python and SQL daily.")
    result = match_mod.score(hit, profile, CRITERIA)
    named = next(r for r in result.reasons if "Names your" in r)
    assert "Python" in named and "SQL" in named


def test_a_skill_the_profile_lacks_is_never_credited(profile):
    hit = listing(title="Backend Engineer", snippet="Rust, Elixir and COBOL.")
    result = match_mod.score(hit, profile, CRITERIA)
    assert not any("Names your" in r for r in result.reasons)


@pytest.mark.parametrize("field, value, blacklist", [
    ("company", "Wayfair", {"company_blacklist": ["wayfair"]}),
    ("title", "Senior Sales Engineer", {"title_blacklist": ["Sales"]}),
    ("location", "São Paulo, Brazil", {"location_blacklist": ["Brazil"]}),
])
def test_a_blacklisted_listing_is_excluded_with_a_reason(profile, field, value, blacklist):
    criteria = CRITERIA.model_copy(update=blacklist)
    result = match_mod.score(listing(**{field: value}), profile, criteria)
    assert result.is_excluded
    assert field in result.excluded.lower()


def test_an_old_posting_is_excluded_only_when_you_set_a_limit(profile):
    old = listing(posted="2020-01-01")
    assert not match_mod.score(old, profile, CRITERIA).is_excluded
    limited = CRITERIA.model_copy(update={"posted_within_days": 30})
    assert match_mod.score(old, profile, limited).is_excluded


def test_an_undated_posting_is_never_treated_as_an_old_one(profile):
    limited = CRITERIA.model_copy(update={"posted_within_days": 7})
    assert not match_mod.score(listing(posted=""), profile, limited).is_excluded


# --- the queue remembers what you decided -----------------------------------

def candidate(score=60, **kwargs) -> Candidate:
    return Candidate(listing=listing(**kwargs), match=Match(score=score))


def test_the_queue_is_ordered_by_score(home):
    queue_store.save([candidate(40, url="https://x.com/1"),
                      candidate(90, url="https://x.com/2")], home)
    assert [c.match.score for c in queue_store.load(home)] == [90, 40]


def test_a_second_search_does_not_duplicate_a_listing(home):
    queue_store.save([candidate()], home)
    merged, added = queue_store.merge(queue_store.load(home), [candidate()])
    assert len(merged) == 1 and added == 0


def test_a_dismissal_survives_the_next_search(home):
    queue_store.save([candidate()], home)
    dropped = queue_store.load(home)[0]
    queue_store.set_status(dropped.id, queue_store.DISMISSED, home)

    merged, _ = queue_store.merge(queue_store.load(home), [candidate(score=99)])
    assert merged[0].status == queue_store.DISMISSED
    assert merged[0].match.score == 99  # the score still refreshes underneath


def test_picking_records_the_job_it_became(home):
    queue_store.save([candidate()], home)
    stored = queue_store.load(home)[0]
    updated = queue_store.set_status(stored.id, queue_store.PICKED, home, job_slug="acme-be")
    assert updated.job_slug == "acme-be"
    assert queue_store.counts(home)["picked"] == 1


def test_an_unknown_id_decides_nothing(home):
    assert queue_store.set_status("nope", queue_store.DISMISSED, home) is None


def test_clearing_one_state_leaves_the_others(home):
    queue_store.save([candidate(url="https://x.com/1"), candidate(url="https://x.com/2")], home)
    first = queue_store.load(home)[0]
    queue_store.set_status(first.id, queue_store.DISMISSED, home)
    assert queue_store.clear(home, status=queue_store.DISMISSED) == 1
    assert len(queue_store.load(home)) == 1


def test_a_corrupt_queue_file_reads_as_empty(home):
    queue_store.queue_path(home).write_text("- [broken")
    assert queue_store.load(home) == []


# --- the board adapters, on payloads they really receive --------------------

GREENHOUSE_PAYLOAD = {"jobs": [
    {"absolute_url": "https://boards.greenhouse.io/acme/jobs/1", "title": "Backend Engineer",
     "location": {"name": "Zurich"}, "updated_at": "2026-09-01T10:00:00-04:00"},
    {"absolute_url": "", "title": "Broken"},
]}
LEVER_PAYLOAD = [
    {"hostedUrl": "https://jobs.lever.co/acme/1", "text": "Backend Engineer",
     "categories": {"location": "Zurich", "commitment": "Full-time",
                    "workplaceType": "hybrid"},
     "createdAt": 1788220800000, "descriptionPlain": "<p>Own the ledger.</p>"},
]
ASHBY_PAYLOAD = {"jobs": [
    {"jobUrl": "https://jobs.ashbyhq.com/acme/1", "title": "Backend Engineer",
     "location": "Zurich", "isRemote": True, "publishedAt": "2026-09-01T00:00:00Z"},
]}


@pytest.mark.parametrize("fn, payload, expected_source", [
    (ats.greenhouse, GREENHOUSE_PAYLOAD, "greenhouse"),
    (ats.lever, LEVER_PAYLOAD, "lever"),
    (ats.ashby, ASHBY_PAYLOAD, "ashby"),
])
def test_a_board_payload_becomes_listings(monkeypatch, fn, payload, expected_source):
    monkeypatch.setattr(ats, "_get_json", lambda *a, **k: payload)
    found = fn("acme")
    assert len(found) == 1  # the entry with no URL is dropped
    assert found[0].title == "Backend Engineer"
    assert found[0].location == "Zurich"
    assert found[0].posted == "2026-09-01"
    assert found[0].source == expected_source


def test_a_board_description_arrives_as_text_not_markup(monkeypatch):
    monkeypatch.setattr(ats, "_get_json", lambda *a, **k: LEVER_PAYLOAD)
    assert ats.lever("acme")[0].snippet == "Own the ledger."


def test_an_unknown_source_name_is_an_error():
    with pytest.raises(sources.SourceError, match="No such source"):
        sources.run("monster", "", CRITERIA)


# --- the page adapter's parsing, without a browser --------------------------

@pytest.mark.parametrize("text, expected", [
    ("Senior Backend Engineer\nZurich, Switzerland\nFull time", "Senior Backend Engineer"),
    ("Backend Engineer • Engineering • Remote", "Backend Engineer"),
    ("  Design Engineer  ", "Design Engineer"),
])
def test_a_card_s_title_is_its_first_line_not_the_whole_card(text, expected):
    assert page.title_of(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("Backend Engineer\nZurich, Switzerland", "Zurich"),
    ("Data Engineer\nSan Francisco, CA", "San Francisco, CA"),
    ("Backend Engineer • Remote - EU • Full time", "Remote - EU"),
    ("AI Strategist\nFinancial Partnerships Manager, International", ""),
    ("Backend Engineer", ""),
])
def test_a_location_is_only_read_when_the_card_states_one(text, expected):
    assert page.location_of(text, CRITERIA) == expected


def test_page_furniture_is_not_a_job():
    for text in ("Apply now", "Create alert", "Sign in"):
        assert page.to_listing({"url": "https://x.com/jobs/1", "text": text}, CRITERIA) is None


def test_a_board_s_own_login_page_is_not_a_job():
    row = {"url": "https://x.com/users/sign_in", "text": "Backend Engineer"}
    assert page.to_listing(row, CRITERIA) is None


def test_a_card_that_is_really_the_whole_list_is_not_read_for_context():
    """Some boards render every posting inside one element."""
    row = {"url": "https://x.com/jobs/1", "text": "Backend Engineer",
           "context": "Backend Engineer\nZurich\n" + "Another Job\nBerlin\n" * 60}
    found = page.to_listing(row, CRITERIA)
    assert found.location == ""  # rather than a location belonging to another job
    assert "Another Job" not in found.snippet


# --- the search engines, without a browser ----------------------------------

def test_linkedin_builds_the_search_it_was_asked_for():
    url = linkedin.search_url(Criteria(titles=["Backend Engineer"], locations=["Zurich"],
                                       posted_within_days=7))
    assert "keywords=Backend+Engineer" in url
    assert "location=Zurich" in url
    assert "f_TPR=r604800" in url  # a week, as LinkedIn counts it


def test_linkedin_asks_for_remote_only_when_that_is_all_you_want():
    remote_only = Criteria(titles=["x"], remote=True, hybrid=False, onsite=False)
    assert "f_WT=2" in linkedin.search_url(remote_only)
    assert "f_WT" not in linkedin.search_url(Criteria(titles=["x"]))


def test_indeed_builds_the_search_it_was_asked_for():
    url = indeed.search_url(Criteria(titles=["Backend Engineer"], locations=["Berlin"],
                                     posted_within_days=14))
    assert "q=Backend+Engineer" in url and "l=Berlin" in url and "fromage=14" in url


def test_each_location_is_searched_in_its_own_run():
    """One run per place, because these engines take one place at a time."""
    criteria = Criteria(titles=["x"], locations=["Zurich, Switzerland", "Berlin, Germany"],
                        linkedin=True)
    assert sources.targets(criteria)["linkedin"] == ["Zurich, Switzerland", "Berlin, Germany"]


def test_an_engine_with_no_location_still_runs_once():
    assert sources.targets(Criteria(titles=["x"], linkedin=True))["linkedin"] == [""]


def test_the_location_being_searched_reaches_the_url():
    criteria = Criteria(titles=["x"], locations=["Zurich, Switzerland", "Berlin, Germany"])
    assert "Berlin" in linkedin.search_url(criteria, "Berlin, Germany")
    assert "Zurich" not in linkedin.search_url(criteria, "Berlin, Germany")


def test_a_linkedin_card_becomes_a_listing():
    found = linkedin.to_listings([
        {"url": "https://www.linkedin.com/jobs/view/1", "title": "Backend Engineer",
         "company": "Acme", "location": "Zurich", "posted": "2026-09-01T00:00:00Z"},
        {"title": "No link here"},
    ])
    assert len(found) == 1
    assert found[0].posted == "2026-09-01"
    assert found[0].source == "linkedin"


def test_an_indeed_card_becomes_a_listing():
    found = indeed.to_listings([
        {"url": "https://www.indeed.com/viewjob?jk=1", "title": "Backend Engineer",
         "company": "Acme", "location": "Berlin", "snippet": "Python and Postgres."},
    ])
    assert found[0].snippet == "Python and Postgres."
    assert found[0].source == "indeed"


def test_a_sign_in_wall_is_reported_as_advice(monkeypatch):
    monkeypatch.setattr(linkedin, "read", lambda *a, **k: {"wall": True, "rows": []})
    with pytest.raises(BrowserError, match="sign-in wall"):
        linkedin.search(Criteria(titles=["x"]))


def test_an_anti_bot_challenge_is_reported_as_advice(monkeypatch):
    monkeypatch.setattr(indeed, "read", lambda *a, **k: {"blocked": True, "rows": []})
    with pytest.raises(BrowserError, match="anti-bot"):
        indeed.search(Criteria(titles=["x"]))


def test_an_empty_result_page_is_not_an_error(monkeypatch):
    monkeypatch.setattr(linkedin, "read", lambda *a, **k: {"wall": False, "rows": []})
    assert linkedin.search(Criteria(titles=["x"])) == []


# --- the whole pass ---------------------------------------------------------

def test_a_dead_source_does_not_lose_the_others(monkeypatch):
    def run(name, target, criteria, **kwargs):
        if target == "dead":
            raise sources.SourceError("No board found - check the slug.")
        return [listing(url=f"https://x.com/{target}")]

    monkeypatch.setattr(sources, "run", run)
    criteria = CRITERIA.model_copy(update={"greenhouse": ["dead", "alive"]})
    found, outcomes = discover.collect(criteria)

    assert len(found) == 1
    assert {o.target: bool(o.error) for o in outcomes} == {"dead": True, "alive": False}


def test_an_adapter_that_crashes_is_reported_not_raised(monkeypatch):
    def explode(*args, **kwargs):
        raise ValueError("selector changed")

    monkeypatch.setattr(sources, "run", explode)
    _, outcomes = discover.collect(CRITERIA)
    assert "ValueError" in outcomes[0].error


def test_one_posting_on_two_boards_is_collected_once(monkeypatch):
    monkeypatch.setattr(sources, "run",
                        lambda name, target, criteria, **kw: [listing(source=name)])
    criteria = CRITERIA.model_copy(update={"lever": ["acme"]})
    found, _ = discover.collect(criteria)
    assert len(found) == 1


def test_a_search_scores_queues_and_counts(home, profile, monkeypatch):
    monkeypatch.setattr(sources, "run", lambda *a, **k: [
        listing(url="https://x.com/1", title="Backend Engineer"),
        listing(url="https://x.com/2", title="Head of Catering", location="Rome"),
    ])
    report = discover.search(profile, CRITERIA, home)

    assert report.found == 2
    assert report.queued == 1 and report.added == 1
    assert report.below == 1  # the catering job scored, and scored too low
    assert [c.listing.title for c in queue_store.load(home)] == ["Backend Engineer"]


def test_searching_twice_adds_nothing_the_second_time(home, profile, monkeypatch):
    monkeypatch.setattr(sources, "run",
                        lambda *a, **k: [listing(title="Backend Engineer")])
    discover.search(profile, CRITERIA, home)
    assert discover.search(profile, CRITERIA, home).added == 0


def test_only_searches_the_source_you_named(monkeypatch):
    seen = []
    monkeypatch.setattr(sources, "run",
                        lambda name, target, criteria, **kw: seen.append(name) or [])
    criteria = CRITERIA.model_copy(update={"lever": ["acme"], "pages": ["https://x.com"]})
    discover.collect(criteria, only=("lever",))
    assert seen == ["lever"]


def test_the_summary_says_what_happened(home, profile, monkeypatch):
    monkeypatch.setattr(sources, "run", lambda *a, **k: [listing(title="Backend Engineer")])
    assert "1 found" in discover.search(profile, CRITERIA, home).summary()


# --- a place is named more fully by a board than by a person ----------------

@pytest.mark.parametrize("wanted, where", [
    ("Munich, Germany", "Munich, Bavaria, Germany"),
    ("Zurich, Switzerland", "Zurich, Zurich, Switzerland"),
    ("Paris, France", "Paris, Ile-de-France, France"),
    ("Germany", "Munich, Bavaria, Germany"),
    ("Munich, Germany", "Germany"),
])
def test_a_qualified_city_still_matches_the_place(profile, wanted, where):
    """The search engines need 'Munich, Germany' to resolve it; scoring must
    not then charge you for writing it that way."""
    criteria = CRITERIA.model_copy(update={"locations": [wanted]})
    result = match_mod.score(listing(title="Backend Engineer", location=where),
                             profile, criteria)
    assert any(f"In {wanted}" in reason for reason in result.reasons)


@pytest.mark.parametrize("where", ["Berlin, Germany", "Solna, Stockholm County, Sweden"])
def test_a_different_city_is_still_a_different_city(profile, where):
    criteria = CRITERIA.model_copy(update={"locations": ["Munich, Germany"]})
    result = match_mod.score(listing(title="Backend Engineer", location=where),
                             profile, criteria)
    assert any("not one you asked for" in reason for reason in result.reasons)
