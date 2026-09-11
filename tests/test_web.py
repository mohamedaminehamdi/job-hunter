"""The web layer: that each route calls the right thing and shows the result.

The library is stubbed where it would reach a browser or a provider. What is
under test is the shell - status codes, redirects, and the review step's promise
that a blocked document does not become a file.
"""

import json

import pytest
from fastapi.testclient import TestClient

from job_hunter import render
from job_hunter.apply import store as apply_store
from job_hunter.discover import criteria as criteria_mod
from job_hunter.discover import sources
from job_hunter.discover import store as queue_store
from job_hunter.discover.criteria import Criteria
from job_hunter.discover.models import Listing
from job_hunter.generate import cover_letter, cv
from job_hunter.generate import store as doc_store
from job_hunter.jobs import parse as job_parse
from job_hunter.jobs import store as job_store
from job_hunter.jobs.fetch import FetchError
from job_hunter.profile import store as profile_store
from job_hunter.web import create_app

CV_REPLY = {"summary": "Engineer.", "roles": [{"index": 0}], "projects": [], "skills": ["Python"]}
LETTER_REPLY = {"greeting": "Dear Hiring Team,", "paragraphs": ["I build pipelines."],
                "closing": "Kind regards,"}
SLUG = "zeta-senior-data-engineer"


@pytest.fixture
def client(home):
    """A client whose app reads the isolated home. Redirects are not followed."""
    return TestClient(create_app(), follow_redirects=False)


@pytest.fixture
def populated(client, home, profile, job):
    profile_store.save(profile, profile_store.profile_path(home))
    job_store.save(job, home)
    return client


# --- pages ----------------------------------------------------------------

def test_dashboard_renders_with_nothing_saved(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Add a job" in response.text
    assert "No profile yet" in response.text


def test_dashboard_lists_jobs_and_the_profile(populated):
    body = populated.get("/").text
    assert "Senior Data Engineer at Zeta" in body
    assert "Ada Lovelace" in body


def test_profile_page_shows_the_yaml(populated):
    body = populated.get("/profile").text
    assert "personal:" in body
    assert "Lovelace" in body


def test_job_page_shows_the_posting(populated):
    body = populated.get(f"/jobs/{SLUG}").text
    assert "Strong Python" in body
    assert "#7b2ff7" in body  # the company colour it read off the page


def test_unknown_job_is_a_404_page_not_a_crash(client):
    response = client.get("/jobs/ghost")
    assert response.status_code == 404
    assert "no saved job" in response.text.lower()


def test_review_before_generating_is_a_404(populated):
    assert populated.get(f"/jobs/{SLUG}/cv").status_code == 404


def test_source_route_is_not_shadowed_by_the_review_route(populated):
    """/jobs/{slug}/source must not be read as a document kind."""
    response = populated.get(f"/jobs/{SLUG}/source")
    assert response.status_code == 200
    assert "Senior Data Engineer at Zeta" in response.text


# --- actions --------------------------------------------------------------

def test_adding_a_job_with_neither_url_nor_text_complains(client):
    response = client.post("/jobs", data={"url": "", "text": ""})
    assert response.status_code == 303
    assert "error=Paste" in response.headers["location"]


def test_adding_a_job_from_a_url(client, home, monkeypatch, job):
    monkeypatch.setattr(job_parse, "from_url", lambda url, **kw: job)
    response = client.post("/jobs", data={"url": "https://example.com/jobs/42"})
    assert response.headers["location"] == f"/jobs/{SLUG}?note=Added."
    assert job_store.load(SLUG, home) is not None


def test_a_fetch_failure_becomes_a_message_on_the_dashboard(client, monkeypatch):
    def explode(url, **kwargs):
        raise FetchError("That page is behind a login.")

    monkeypatch.setattr(job_parse, "from_url", explode)
    response = client.post("/jobs", data={"url": "https://example.com/x"})
    assert response.status_code == 303
    assert response.headers["location"].startswith("/?error=That+page+is+behind")


def test_adding_a_job_from_pasted_text(client, home, stub_llm):
    stub_llm(json.dumps({"title": "Data Engineer", "company": "Acme",
                         "description": "A real description. " * 20,
                         "requirements": ["Python"]}))
    response = client.post("/jobs", data={"text": "Acme is hiring..."})
    assert response.status_code == 303
    assert job_store.load("acme-data-engineer", home) is not None


def test_importing_a_cv_saves_the_profile(client, home):
    files = {"file": ("me.yaml", b"personal:\n  name: Ada\n  surname: Lovelace\n",
                      "application/x-yaml")}
    response = client.post("/profile/import", files=files)
    assert response.status_code == 303
    assert profile_store.load(profile_store.profile_path(home)).personal.name == "Ada"


def test_importing_a_bad_file_reports_it(client):
    files = {"file": ("me.pages", b"nonsense", "application/octet-stream")}
    response = client.post("/profile/import", files=files)
    assert "error=Unsupported" in response.headers["location"]


def test_saving_hand_edited_yaml(client, home):
    response = client.post("/profile", data={"yaml_text": "personal:\n  name: Grace\n"})
    assert response.status_code == 303
    assert profile_store.load(profile_store.profile_path(home)).personal.name == "Grace"


def test_saving_invalid_yaml_is_refused_with_a_message(client):
    response = client.post("/profile", data={"yaml_text": "personal: [unclosed"})
    assert "error=That+is+not+valid+YAML" in response.headers["location"]


def test_generating_a_cv_then_reviewing_it(populated, home, stub_llm):
    stub_llm(json.dumps(CV_REPLY))
    response = populated.post(f"/jobs/{SLUG}/cv")
    assert response.status_code == 303
    assert response.headers["location"].startswith(f"/jobs/{SLUG}/cv")

    review = populated.get(f"/jobs/{SLUG}/cv")
    assert review.status_code == 200
    assert "Check before sending" in review.text
    assert "Export PDF" in review.text

    preview = populated.get(f"/jobs/{SLUG}/cv/preview")
    assert "Ada Lovelace" in preview.text
    assert "<!doctype html>" in preview.text.lower()


def test_a_generation_failure_lands_back_on_the_job_page(populated, stub_llm):
    stub_llm("I'm sorry, I can't help with that.")
    response = populated.post(f"/jobs/{SLUG}/cv")
    assert response.headers["location"].startswith(f"/jobs/{SLUG}?error=")


def test_drafting_an_answer(populated, home, stub_llm):
    stub_llm(json.dumps({"answer": "No, I have not used Terraform.", "unsupported": ""}))
    response = populated.post(f"/jobs/{SLUG}/answers",
                              data={"question": "Terraform?", "words": "80"})
    assert response.status_code == 303
    assert len(doc_store.load_answers(SLUG, home)) == 1
    assert "No, I have not used Terraform." in populated.get(f"/jobs/{SLUG}").text


def test_the_job_page_shows_what_the_guard_found_in_an_answer(populated, stub_llm):
    """The findings were computed and saved, but only the CLI was showing them."""
    stub_llm(json.dumps({"answer": "Yes, I ran Kubernetes for 9 years.",
                         "unsupported": "The profile shows no Kubernetes experience."}))
    populated.post(f"/jobs/{SLUG}/answers", data={"question": "Kubernetes?", "words": "80"})

    page = populated.get(f"/jobs/{SLUG}").text
    assert "Kubernetes" in page
    assert "The figure &#39;9&#39; is not in your profile" in page
    assert "flagged a gap" in page


def test_an_empty_question_is_refused(populated):
    response = populated.post(f"/jobs/{SLUG}/answers", data={"question": "  "})
    assert "error=Type+the+question" in response.headers["location"]


# --- discovery ------------------------------------------------------------

SEARCH = Criteria(titles=["Data Engineer"], locations=["Berlin"],
                  greenhouse=["acme"], min_score=30)


@pytest.fixture
def searchable(populated, home, monkeypatch):
    criteria_mod.save(SEARCH, home)
    monkeypatch.setattr(sources, "run", lambda *a, **k: [
        Listing(url="https://boards.example.com/jobs/1", title="Data Engineer",
                company="Acme", location="Berlin", source="greenhouse"),
    ])
    return populated


def test_the_queue_page_renders_empty(client):
    response = client.get("/queue")
    assert response.status_code == 200
    assert "Nothing here yet" in response.text


def test_an_unconfigured_search_is_refused_with_a_reason(populated):
    response = populated.post("/search")
    assert "error=" in response.headers["location"]
    assert "title" in response.headers["location"]


def test_searching_fills_the_queue_and_says_so(searchable, home):
    response = searchable.post("/search")
    assert response.status_code == 303
    assert "note=" in response.headers["location"]
    assert len(queue_store.load(home)) == 1

    page = searchable.get("/queue").text
    assert "Data Engineer" in page
    assert "Title matches" in page  # the score explains itself on the page


def test_a_failing_source_shows_its_message(populated, home, monkeypatch):
    criteria_mod.save(SEARCH, home)
    monkeypatch.setattr(sources, "run", lambda *a, **k: (_ for _ in ()).throw(
        sources.SourceError("No board found - check the slug.")))
    response = populated.post("/search")
    assert "check+the+slug" in response.headers["location"]


def test_picking_saves_the_job_and_goes_to_it(searchable, home, monkeypatch, job):
    searchable.post("/search")
    candidate_id = queue_store.load(home)[0].id
    monkeypatch.setattr(job_parse, "from_url", lambda *a, **k: job)

    response = searchable.post(f"/queue/{candidate_id}/pick")
    assert response.headers["location"].startswith(f"/jobs/{job.slug}")
    assert queue_store.get(candidate_id, home).status == queue_store.PICKED


def test_a_posting_that_will_not_load_leaves_it_in_the_queue(searchable, home, monkeypatch):
    searchable.post("/search")
    candidate_id = queue_store.load(home)[0].id
    monkeypatch.setattr(job_parse, "from_url", lambda *a, **k: (_ for _ in ()).throw(
        FetchError("The page did not finish loading in time.")))

    response = searchable.post(f"/queue/{candidate_id}/pick")
    assert "error=" in response.headers["location"]
    assert queue_store.get(candidate_id, home).status == queue_store.NEW


def test_dismissing_from_the_page(searchable, home):
    searchable.post("/search")
    candidate_id = queue_store.load(home)[0].id
    assert searchable.post(f"/queue/{candidate_id}/dismiss").status_code == 303
    assert queue_store.get(candidate_id, home).status == queue_store.DISMISSED


def test_deciding_on_a_listing_that_is_gone_is_a_message_not_a_crash(populated):
    response = populated.post("/queue/no-such-listing/dismiss")
    assert response.status_code == 303
    assert "no+longer+in+the+queue" in response.headers["location"]


def test_saving_the_search_yaml(populated, home):
    response = populated.post("/search/criteria",
                              data={"yaml_text": "titles:\n  - Platform Engineer\n"})
    assert response.status_code == 303
    assert criteria_mod.load(home).titles == ["Platform Engineer"]


def test_saving_invalid_search_yaml_is_refused(populated):
    response = populated.post("/search/criteria", data={"yaml_text": "titles: [unclosed"})
    assert "not+valid+YAML" in response.headers["location"]


def test_clearing_the_queue(searchable, home):
    searchable.post("/search")
    assert searchable.post("/queue/clear", data={"status": ""}).status_code == 303
    assert queue_store.load(home) == []


# --- what you actually sent -----------------------------------------------

def test_the_job_page_offers_to_mark_it_applied(populated):
    page = populated.get(f"/jobs/{SLUG}").text
    assert "Mark as applied" in page
    assert f"/jobs/{SLUG}/applied" in page


def test_marking_applied_from_the_job_page(populated, home):
    response = populated.post(f"/jobs/{SLUG}/applied",
                              data={"on": "2026-08-24", "channel": "company form",
                                    "sent": ["cv"], "contact": "Nadia"})
    assert response.status_code == 303
    application = apply_store.load(SLUG, home)
    assert application.applied_on == "2026-08-24"
    assert application.sent == ["cv"]


def test_the_job_page_then_shows_what_you_sent_and_when(populated, home):
    populated.post(f"/jobs/{SLUG}/applied",
                   data={"on": "2026-08-24", "channel": "company form"})
    page = populated.get(f"/jobs/{SLUG}").text
    assert "2026-08-24" in page and "company form" in page
    assert "Mark as applied" not in page


def test_applying_to_a_job_that_is_gone_is_a_message_not_a_crash(client):
    response = client.post("/jobs/no-such-job/applied", data={})
    assert response.status_code == 303
    assert "no+saved+job" in response.headers["location"].lower()


def test_the_applications_page_renders_empty(client):
    response = client.get("/applications")
    assert response.status_code == 200
    assert "Nothing here" in response.text


def test_the_applications_page_lists_what_you_sent(populated, home):
    populated.post(f"/jobs/{SLUG}/applied", data={"channel": "referral"})
    page = populated.get("/applications").text
    assert "referral" in page and SLUG in page


def test_moving_an_application_on_from_the_page(populated, home):
    populated.post(f"/jobs/{SLUG}/applied", data={})
    response = populated.post(f"/applications/{SLUG}/mark",
                              data={"status": "interviewing", "back": "/applications"})
    assert response.status_code == 303
    assert apply_store.load(SLUG, home).status == "interviewing"


def test_an_illegal_move_is_a_message_not_a_crash(populated, home):
    populated.post(f"/jobs/{SLUG}/applied", data={})
    populated.post(f"/applications/{SLUG}/mark", data={"status": "rejected"})
    response = populated.post(f"/applications/{SLUG}/mark", data={"status": "applied"})
    assert "error=" in response.headers["location"]
    assert apply_store.load(SLUG, home).status == "rejected"


def test_noting_something_resets_the_quiet_clock(populated, home):
    populated.post(f"/jobs/{SLUG}/applied", data={"on": "2020-01-01"})
    assert apply_store.load(SLUG, home).is_quiet()

    populated.post(f"/applications/{SLUG}/note", data={"text": "chased them"})
    assert not apply_store.load(SLUG, home).is_quiet()


@pytest.mark.parametrize("back", ["https://evil.example/steal", "//evil.example",
                                  "javascript:alert(1)"])
def test_a_form_cannot_redirect_off_this_site(populated, back):
    """`back` is form input reaching a Location header."""
    populated.post(f"/jobs/{SLUG}/applied", data={})
    response = populated.post(f"/applications/{SLUG}/note",
                              data={"text": "hi", "back": back})
    assert response.headers["location"].startswith("/applications")


def test_the_queue_shows_that_a_picked_listing_was_applied_to(searchable, home, job,
                                                              monkeypatch):
    searchable.post("/search")
    candidate_id = queue_store.load(home)[0].id
    monkeypatch.setattr(job_parse, "from_url", lambda *a, **k: job)
    searchable.post(f"/queue/{candidate_id}/pick")
    searchable.post(f"/jobs/{job.slug}/applied", data={"on": "2026-08-24"})

    assert "applied 2026-08-24" in searchable.get("/queue?show=all").text


def test_the_dashboard_counts_what_is_outstanding(populated, home):
    populated.post(f"/jobs/{SLUG}/applied", data={"on": "2020-01-01"})
    page = populated.get("/").text
    assert "1 out" in page and "no reply" in page


def test_exporting_writes_the_pdf_and_offers_it(populated, home, profile, job,
                                                stub_llm, monkeypatch):
    doc_store.save(cv.assemble(profile, job, CV_REPLY), SLUG, "cv", home)
    monkeypatch.setattr(render, "write_pdf", _fake_pdf())

    response = populated.post(f"/jobs/{SLUG}/cv/export", data={"theme": "neutral"})
    assert response.status_code == 303
    assert "note=Exported" in response.headers["location"]

    pdf = populated.get(f"/download/{SLUG}-cv.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"


def test_a_blocked_document_is_never_exported(populated, home, profile, job, monkeypatch):
    blocked = cv.assemble(profile, job, {**CV_REPLY, "summary": "Engineer at [Company]."})
    doc_store.save(blocked, SLUG, "cv", home)

    def must_not_run(html, path):  # pragma: no cover - the point is it does not
        raise AssertionError("wrote a PDF for a blocked document")

    monkeypatch.setattr(render, "write_pdf", must_not_run)
    response = populated.post(f"/jobs/{SLUG}/cv/export", data={"theme": "neutral"})
    assert "error=" in response.headers["location"]
    assert "not+ready+to+export" in response.headers["location"]

    # And the review page disables the button rather than letting you try.
    assert "disabled" in populated.get(f"/jobs/{SLUG}/cv").text


def test_the_branded_letter_uses_the_company_colour(populated, home, profile, job, monkeypatch):
    doc_store.save(cover_letter.assemble(profile, job, LETTER_REPLY), SLUG, "letter", home)
    seen = {}
    monkeypatch.setattr(render, "write_pdf", _fake_pdf(seen))

    populated.post(f"/jobs/{SLUG}/letter/export", data={"theme": "neutral", "branded": "1"})
    assert "#7b2ff7" in seen["html"]


def test_exporting_something_never_generated_is_refused(populated):
    response = populated.post(f"/jobs/{SLUG}/cv/export", data={"theme": "neutral"})
    assert "error=Generate+the+document+first" in response.headers["location"]


def test_download_refuses_a_path_outside_the_output_directory(client):
    response = client.get("/download/..%2F..%2F..%2Fetc%2Fpasswd")
    assert response.status_code in (303, 404)
    assert "passwd" not in response.text


def test_deleting_a_job(populated, home):
    response = populated.post(f"/jobs/{SLUG}/delete")
    assert response.status_code == 303
    assert job_store.load(SLUG, home) is None


def _fake_pdf(seen: dict | None = None):
    def write(html, path):
        if seen is not None:
            seen["html"] = html
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.4 fake")
        return path

    return write
