"""The CLI: argument wiring, and that a library error prints as one line.

Nothing here touches a browser or a provider - job fetching and PDF writing are
patched out, because what is under test is the plumbing, not the libraries.
"""

import json

import pytest

from job_hunter import cli, render
from job_hunter.apply import models as apply_models
from job_hunter.apply import store as apply_store
from job_hunter.discover import criteria as criteria_mod
from job_hunter.discover import sources
from job_hunter.discover import store as queue_store
from job_hunter.discover.models import Listing
from job_hunter.generate import store as doc_store
from job_hunter.jobs import parse as job_parse
from job_hunter.jobs import store as job_store
from job_hunter.jobs.fetch import FetchError
from job_hunter.profile import store as profile_store

CV_REPLY = {"summary": "Engineer.", "roles": [{"index": 0}], "projects": [], "skills": ["Python"]}


@pytest.fixture
def saved(home, profile, job):
    """A home with a profile and one job already in it."""
    profile_store.save(profile, profile_store.profile_path(home))
    job_store.save(job, home)
    return home


def run(*argv):
    return cli.main(list(argv))


# --- errors ---------------------------------------------------------------

def test_a_library_error_is_one_line_not_a_traceback(home, capsys, monkeypatch):
    def explode(*args, **kwargs):
        raise FetchError("Only http and https URLs can be fetched, not 'file'.")

    monkeypatch.setattr(job_parse, "from_url", explode)
    assert run("job", "file:///etc/passwd") == 1
    captured = capsys.readouterr()
    assert captured.err.strip() == "error: Only http and https URLs can be fetched, not 'file'."
    assert "Traceback" not in captured.err


def test_an_unknown_job_slug_is_a_user_error(saved, capsys):
    assert run("cv", "no-such-job") == 1
    assert "No saved job" in capsys.readouterr().err


def test_no_command_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as caught:
        run()
    assert caught.value.code == 2


# --- doctor / profile / jobs ---------------------------------------------

def test_doctor_reports_json(home, capsys, monkeypatch):
    monkeypatch.setattr(cli, "_browser_status", lambda: None)
    assert run("--json", "doctor") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["model"] == "test/model"
    assert payload["model_ready"] is True
    assert payload["browser_ready"] is True
    assert payload["profile_exists"] is False


def test_doctor_names_what_is_wrong(home, capsys, monkeypatch):
    monkeypatch.delenv("JOB_HUNTER_API_KEY")
    monkeypatch.setattr(cli, "_browser_status", lambda: "Chromium cannot start. Run: x")
    run("doctor")
    out = capsys.readouterr().out
    assert "No API key" in out
    assert "Chromium cannot start" in out


def test_profile_without_one_says_how_to_start(home, capsys):
    assert run("profile") == 1
    assert "Import a CV" in capsys.readouterr().out


def test_profile_lists_the_checklist(saved, capsys):
    assert run("profile") == 0
    out = capsys.readouterr().out
    assert "Ada Lovelace" in out
    assert "2 role(s)" in out


def test_import_yaml_needs_no_model(home, tmp_path, capsys):
    source = tmp_path / "me.yaml"
    source.write_text("personal:\n  name: Ada\n  surname: Lovelace\n"
                      "experience:\n  - position: Dev\n    company: Acme\n",
                      encoding="utf-8")
    assert run("import", str(source)) == 0
    assert profile_store.load(profile_store.profile_path(home)).personal.name == "Ada"
    assert "model" not in capsys.readouterr().out.lower()


def test_import_flags_that_a_model_read_it(home, tmp_path, capsys, stub_llm):
    stub_llm(json.dumps({"personal": {"name": "Ada", "surname": "Lovelace"},
                         "experience": [{"position": "Dev", "company": "Acme"}]}))
    source = tmp_path / "cv.txt"
    source.write_text("Ada Lovelace\nDev at Acme", encoding="utf-8")
    assert run("import", str(source)) == 0
    assert "check the YAML" in capsys.readouterr().out


def test_jobs_lists_saved_jobs(saved, capsys):
    assert run("jobs") == 0
    assert "zeta-senior-data-engineer" in capsys.readouterr().out


def test_jobs_json(saved, capsys):
    run("--json", "jobs")
    payload = json.loads(capsys.readouterr().out)
    assert payload["jobs"][0]["slug"] == "zeta-senior-data-engineer"
    assert payload["jobs"][0]["usable"] is True


def test_empty_jobs_list_suggests_the_next_step(home, capsys):
    assert run("jobs") == 0
    assert "job-hunter job <url>" in capsys.readouterr().out


# --- job intake -----------------------------------------------------------

def test_job_from_stdin_text(home, capsys, monkeypatch, stub_llm):
    stub_llm(json.dumps({"title": "Data Engineer", "company": "Acme",
                         "description": "A long description. " * 20,
                         "requirements": ["Python"]}))
    monkeypatch.setattr("sys.stdin", _Stdin("Acme is hiring a Data Engineer..."))
    assert run("job", "-") == 0

    out = capsys.readouterr().out
    assert "Data Engineer at Acme" in out
    assert job_store.load("acme-data-engineer", home) is not None


def test_job_url_is_fetched(home, monkeypatch, job, capsys):
    monkeypatch.setattr(job_parse, "from_url", lambda url, **kw: job)
    assert run("job", "https://example.com/jobs/42") == 0
    assert job_store.load(job.slug, home) is not None


def test_a_thin_job_is_still_saved_but_flagged(home, monkeypatch, capsys):
    from job_hunter.jobs.models import Job

    monkeypatch.setattr(job_parse, "from_url", lambda url, **kw: Job(title="Dev", company="Acme"))
    assert run("job", "https://example.com/x") == 0
    assert "no description to work from" in capsys.readouterr().out


def _fake_pdf(seen: dict):
    """Stand in for `write_pdf`, doing the little it promises: a file at `path`."""
    def write(html, path):
        seen["html"] = html
        seen["path"] = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.4 fake")
        return path

    return write


class _Stdin:
    def __init__(self, text):
        self._text = text

    def read(self):
        return self._text


# --- generation -----------------------------------------------------------

def test_cv_tailors_saves_and_reports(saved, capsys, stub_llm):
    stub_llm(json.dumps(CV_REPLY))
    assert run("cv", "zeta-senior-data-engineer") == 0

    out = capsys.readouterr().out
    assert "Tailored CV for Senior Data Engineer at Zeta" in out
    assert "--export" in out  # tells you how to get the PDF
    assert doc_store.load("zeta-senior-data-engineer", "cv", saved) is not None


def test_cv_export_writes_a_pdf(saved, capsys, stub_llm, monkeypatch):
    stub_llm(json.dumps(CV_REPLY))
    written = {}
    monkeypatch.setattr(render, "write_pdf", _fake_pdf(written))
    assert run("cv", "zeta-senior-data-engineer", "--export") == 0
    assert written["path"].name == "zeta-senior-data-engineer-cv.pdf"
    assert "PDF:" in capsys.readouterr().out


def test_export_of_a_blocked_document_is_an_error(saved, capsys, stub_llm):
    stub_llm(json.dumps({**CV_REPLY, "summary": "Engineer at [Company]."}))
    assert run("cv", "zeta-senior-data-engineer", "--export") == 1
    assert "not ready to export" in capsys.readouterr().err


def test_letter_prints_the_letter(saved, capsys, stub_llm):
    stub_llm(json.dumps({"greeting": "Dear Hiring Team,",
                         "paragraphs": ["I build data pipelines."],
                         "closing": "Kind regards,"}))
    assert run("letter", "zeta-senior-data-engineer") == 0
    out = capsys.readouterr().out
    assert "Dear Hiring Team," in out
    assert "Ada Lovelace" in out


def test_letter_branded_uses_the_company_colour(saved, stub_llm, monkeypatch):
    stub_llm(json.dumps({"greeting": "Dear Hiring Team,",
                         "paragraphs": ["I build data pipelines."],
                         "closing": "Kind regards,"}))
    seen = {}
    monkeypatch.setattr(render, "write_pdf", _fake_pdf(seen))
    assert run("letter", "zeta-senior-data-engineer", "--export", "--branded") == 0
    assert "#7b2ff7" in seen["html"]


def test_answer_drafts_and_saves(saved, capsys, stub_llm):
    stub_llm(json.dumps({"answer": "No. I have not used Terraform.",
                         "unsupported": "The profile shows no Terraform experience."}))
    assert run("answer", "zeta-senior-data-engineer", "Terraform experience?") == 0

    out = capsys.readouterr().out
    assert "No. I have not used Terraform." in out
    assert "flagged a gap" in out
    assert len(doc_store.load_answers("zeta-senior-data-engineer", saved)) == 1


def test_answer_does_not_advertise_a_flag_it_lacks(saved, capsys, stub_llm):
    """`answer` writes no PDF, so the export hint would name a flag that errors."""
    stub_llm(json.dumps({"answer": "No. I have not used Terraform.", "unsupported": ""}))
    run("answer", "zeta-senior-data-engineer", "Terraform experience?")
    assert "--export" not in capsys.readouterr().out


# --- discovery ------------------------------------------------------------

SEARCH = criteria_mod.Criteria(titles=["Data Engineer"], locations=["Berlin"],
                               greenhouse=["acme"], min_score=30)


@pytest.fixture
def searchable(saved, monkeypatch):
    """A home ready to search, with one board that always returns one job."""
    criteria_mod.save(SEARCH, saved)
    monkeypatch.setattr(sources, "run", lambda *a, **k: [
        Listing(url="https://boards.example.com/jobs/1", title="Data Engineer",
                company="Acme", location="Berlin", source="greenhouse"),
    ])
    return saved


def test_search_without_criteria_says_what_to_write(home, capsys):
    assert run("search") == 1
    out = capsys.readouterr().out
    assert "titles" in out
    assert "Backend Engineer" in out  # the example it prints to start from


def test_search_queues_what_it_finds(searchable, capsys):
    assert run("search") == 0
    assert "1 found" in capsys.readouterr().out
    assert len(queue_store.load(searchable)) == 1


def test_a_failing_source_is_reported_and_the_command_still_succeeds(saved, monkeypatch, capsys):
    criteria_mod.save(SEARCH, saved)
    monkeypatch.setattr(sources, "run", lambda *a, **k: (_ for _ in ()).throw(
        sources.SourceError("No board found - check the slug.")))
    assert run("search") == 0
    assert "check the slug" in capsys.readouterr().out


def test_queue_lists_what_is_waiting_and_why(searchable, capsys):
    run("search")
    run("queue", "--why")
    out = capsys.readouterr().out
    assert "Data Engineer" in out
    assert "Title matches" in out


def test_queue_is_empty_before_a_search(home, capsys):
    assert run("queue") == 0
    assert "job-hunter search" in capsys.readouterr().out


def test_picking_fetches_the_posting_and_marks_the_candidate(searchable, monkeypatch,
                                                             capsys, job):
    run("search")
    candidate_id = queue_store.load(searchable)[0].id
    monkeypatch.setattr(job_parse, "from_url", lambda *a, **k: job)

    assert run("pick", candidate_id) == 0
    assert queue_store.get(candidate_id, searchable).status == queue_store.PICKED
    assert queue_store.get(candidate_id, searchable).job_slug == job.slug
    assert job_store.load(job.slug, searchable) is not None


def test_dismissing_keeps_it_out_of_the_next_search(searchable):
    run("search")
    candidate_id = queue_store.load(searchable)[0].id
    run("dismiss", candidate_id)

    run("search")
    assert queue_store.get(candidate_id, searchable).status == queue_store.DISMISSED


def test_picking_something_that_is_not_queued_is_one_line(home, capsys):
    assert run("pick", "no-such-listing") == 1


def test_search_json_output_is_machine_readable(searchable, capsys):
    run("--json", "search")
    payload = json.loads(capsys.readouterr().out)
    assert payload["found"] == 1
    assert payload["outcomes"][0]["source"] == "greenhouse"


# --- what you actually sent -----------------------------------------------

def test_recording_an_application_saves_it_and_says_where(saved, capsys):
    assert run("applied", "zeta-senior-data-engineer", "--channel", "company form") == 0
    out = capsys.readouterr().out
    assert "Applied to" in out and "company form" in out
    assert apply_store.load("zeta-senior-data-engineer", saved) is not None


def test_applying_to_a_job_that_is_not_saved_is_one_line(home, capsys):
    assert run("applied", "no-such-job") == 1
    assert "No saved job" in capsys.readouterr().err


def test_it_names_the_documents_you_have_but_does_not_record_them(saved, capsys, stub_llm):
    """What you attached is a fact the tool cannot observe, so it asks."""
    stub_llm(json.dumps(CV_REPLY))
    run("cv", "zeta-senior-data-engineer")
    capsys.readouterr()

    run("applied", "zeta-senior-data-engineer")
    assert "--with cv" in capsys.readouterr().out
    assert apply_store.load("zeta-senior-data-engineer", saved).sent == []


def test_what_you_say_you_sent_is_recorded(saved):
    run("applied", "zeta-senior-data-engineer", "--with", "cv", "--with", "letter")
    assert apply_store.load("zeta-senior-data-engineer", saved).sent == ["cv", "letter"]


def test_marking_an_application_that_does_not_exist_is_one_line(saved, capsys):
    assert run("mark", "zeta-senior-data-engineer", "rejected") == 1
    assert "Record one first" in capsys.readouterr().err


def test_an_illegal_move_names_the_file_you_can_edit(saved, capsys):
    run("applied", "zeta-senior-data-engineer")
    run("mark", "zeta-senior-data-engineer", "rejected")
    capsys.readouterr()

    assert run("mark", "zeta-senior-data-engineer", "interviewing") == 1
    assert "applications/zeta-senior-data-engineer.yaml" in capsys.readouterr().err


def test_a_note_is_dated_and_kept(saved, capsys):
    run("applied", "zeta-senior-data-engineer")
    assert run("note", "zeta-senior-data-engineer", "chased the recruiter") == 0

    history = apply_store.load("zeta-senior-data-engineer", saved).history
    assert history[-1].note == "chased the recruiter" and history[-1].at


def test_the_listing_says_what_has_gone_quiet(saved, capsys, job):
    run("applied", "zeta-senior-data-engineer", "--on", "2020-01-01")
    capsys.readouterr()
    run("applications")
    assert f"{apply_models.FOLLOW_UP_DAYS}+ days" in capsys.readouterr().out


def test_stale_shows_only_what_is_outstanding(saved, capsys):
    run("applied", "zeta-senior-data-engineer", "--on", "2020-01-01")
    capsys.readouterr()
    assert run("applications", "--stale") == 0
    assert "zeta-senior-data-engineer" in capsys.readouterr().out


def test_applications_is_empty_before_you_send_anything(home, capsys):
    assert run("applications") == 0
    assert "job-hunter applied" in capsys.readouterr().out


def test_applications_json_is_machine_readable(saved, capsys):
    run("applied", "zeta-senior-data-engineer")
    capsys.readouterr()
    run("--json", "applications")
    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["open"] == 1
    assert payload["applications"][0]["job_slug"] == "zeta-senior-data-engineer"


def test_doctor_reports_what_is_outstanding(saved, capsys):
    run("applied", "zeta-senior-data-engineer")
    capsys.readouterr()
    run("doctor")
    assert "1 open" in capsys.readouterr().out


def test_cv_json_output_is_machine_readable(saved, capsys, stub_llm):
    stub_llm(json.dumps(CV_REPLY))
    run("--json", "cv", "zeta-senior-data-engineer")
    payload = json.loads(capsys.readouterr().out)
    assert payload["document"]["summary"] == "Engineer."
    assert payload["exported_to"] is None


def test_generating_without_a_profile_says_to_import_first(home, job, stub_llm):
    job_store.save(job, home)
    stub_llm(json.dumps(CV_REPLY))
    assert run("cv", job.slug) == 1


def test_every_command_is_wired(capsys):
    """A subcommand with no handler would only fail at runtime."""
    parser = cli.build_parser()
    subparsers = [a for a in parser._actions if hasattr(a, "choices") and a.choices]
    names = set(subparsers[0].choices)
    assert names == set(cli.COMMANDS)


def test_it_can_say_which_version_it_is(capsys):
    """The first thing anyone types after installing something."""
    with pytest.raises(SystemExit) as exit_code:
        run("--version")
    assert exit_code.value.code == 0
    assert "job-hunter" in capsys.readouterr().out
