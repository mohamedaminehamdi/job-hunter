"""The skill's Python half, driven exactly as Claude Code drives it.

Claude's whole contribution to a run is four JSON files, so a fixture supplies
them and the entire pipeline executes with no model anywhere. What cannot be
tested here is judgement - whether the tailoring was any good - and mocking that
would only test the mock.
"""

import json

import pytest
import yaml

from job_hunter import paths
from job_hunter.profile import store as profile_store
from job_hunter.skill import exits, runs
from job_hunter.skill.__main__ import main

PAGE = """Senior Data Engineer at Zeta, Berlin.

We run dbt on Postgres and need someone to own the warehouse.

Requirements:
- Experience with dbt
- Deep PostgreSQL knowledge
- Experience running OpenStack in production
- Strong communication skills

Find us at linkedin.com/company/zeta-data
"""

JOB_JSON = {
    "title": "Senior Data Engineer", "company": "Zeta", "location": "Berlin",
    "employment_type": "Full time", "language": "en",
    "description": "Own the warehouse: dbt on Postgres, for the analytics team.",
    "requirements": ["Experience with dbt", "Deep PostgreSQL knowledge",
                     "Experience running OpenStack in production",
                     "Strong communication skills"],
    "responsibilities": ["Own the dbt project"], "nice_to_have": ["Airflow"],
    "keywords": ["dbt", "PostgreSQL", "OpenStack"],
    # Ours to know, not the model's to guess - these must be overridden.
    "url": "https://evil.example/not-the-real-url",
}

SELECTION = {"summary": "Data engineer who rewrote the dbt models.",
             "roles": [{"index": 0, "bullets": ["Cut ETL runtime by 35% with dbt."]}],
             "projects": [], "skills": ["dbt", "Python"]}

DRAFT = {"greeting": "Dear Hiring Team,",
         "paragraphs": ["I rewrote the dbt models at Acme and cut ETL runtime by 35%."],
         "closing": "Kind regards,"}

PLAN = {"targets": [{"tier": "alumni", "why": "Same university"},
                    {"tier": "peer", "title": "Data Engineer", "why": "Future colleague"}],
        "message": {"subject": "dbt at Zeta",
                    "note": "I rewrote the dbt models at Acme. How does Zeta run its "
                            "warehouse day to day?",
                    "inmail": "I rewrote the dbt models at Acme and cut ETL runtime "
                              "by 35%. How does Zeta split ownership of the warehouse?"}}


@pytest.fixture
def repo(tmp_path, monkeypatch, profile):
    """A repo with a profile in it and nothing else."""
    monkeypatch.setenv("JOB_HUNTER_HOME", str(tmp_path))
    (tmp_path / paths.CV_DIR).mkdir()
    (tmp_path / paths.RUNS_DIR).mkdir()
    profile_store.save(profile, profile_store.profile_path())
    return tmp_path


@pytest.fixture
def run_dir(repo):
    """A fetched run, as `skill fetch` would leave it."""
    directory = runs.incoming("https://zeta.example/jobs/1")
    runs.write_text(directory, "page.txt", PAGE)
    runs.write_json(directory, "page.json", {
        "url": "https://zeta.example/jobs/1", "title": "Senior Data Engineer at Zeta",
        "brand_color": "#123456", "text_chars": len(PAGE)})
    return directory


def read(capsys) -> dict:
    """The JSON line the most recent verb printed for the skill to read.

    The last one, not the first: several verbs may have run since the buffer
    was drained, and every one of them prints a line of JSON.
    """
    found = None
    for line in capsys.readouterr().out.splitlines():
        if line.startswith("{"):
            found = json.loads(line)
    assert found is not None, "no verb printed a JSON line"
    return found


# --- the whole pipeline, offline -------------------------------------------

def test_a_full_run_start_to_finish(run_dir, repo, capsys):
    runs.write_json(run_dir, "job.json", JOB_JSON)
    assert main(["job", "--run", str(run_dir)]) == exits.OK
    settled = paths.runs_dir() / read(capsys)["run"].split("/")[-1]

    assert main(["fit", "--run", str(settled), "--when", "before"]) == exits.OK
    before = read(capsys)
    assert before["evidenced"] == 1 and "OpenStack" in before["gaps"]

    runs.write_json(settled, "cv-selection.json", SELECTION)
    assert main(["cv", "--run", str(settled)]) == exits.OK
    assert main(["fit", "--run", str(settled), "--when", "after"]) == exits.OK
    after = read(capsys)
    assert after["evidenced"] == before["evidenced"], "tailoring cannot create evidence"

    runs.write_json(settled, "letter-draft.json", DRAFT)
    assert main(["letter", "--run", str(settled)]) == exits.OK
    runs.write_json(settled, "outreach.json", PLAN)
    assert main(["outreach", "--run", str(settled)]) == exits.OK
    assert main(["report", "--run", str(settled)]) == exits.OK

    produced = {p.name for p in settled.iterdir()}
    assert {"job.yaml", "cv.yaml", "cv.md", "letter.yaml", "letter.md",
            "fit-before.json", "fit-after.json", "outreach.md", "README.md"} <= produced


def test_what_we_observed_beats_what_the_model_wrote(run_dir, capsys):
    """The URL is a fact we hold. A model does not get to overwrite it."""
    runs.write_json(run_dir, "job.json", JOB_JSON)
    main(["job", "--run", str(run_dir)])
    settled = paths.runs_dir() / read(capsys)["run"].split("/")[-1]
    saved = yaml.safe_load((settled / "job.yaml").read_text())
    assert saved["url"] == "https://zeta.example/jobs/1"
    assert saved["brand_color"] == "#123456"


def test_the_run_is_renamed_once_the_job_is_known(run_dir, capsys):
    runs.write_json(run_dir, "job.json", JOB_JSON)
    main(["job", "--run", str(run_dir)])
    assert read(capsys)["run"].endswith("zeta-senior-data-engineer")


# --- failures the skill has to act on ---------------------------------------

@pytest.mark.parametrize("verb, name", [
    ("job", "job.json"), ("cv", "cv-selection.json"),
    ("letter", "letter-draft.json"), ("outreach", "outreach.json"),
])
def test_unreadable_json_says_so_and_does_not_traceback(run_dir, verb, name, capsys):
    runs.write_json(run_dir, "job.json", JOB_JSON)
    main(["job", "--run", str(run_dir)])
    settled = paths.runs_dir() / read(capsys)["run"].split("/")[-1]
    (settled / name).write_text("Here is the JSON you asked for: {oh no")

    assert main([verb, "--run", str(settled)]) == exits.UNREADABLE
    assert "Traceback" not in capsys.readouterr().err


def test_a_posting_too_thin_to_use_stops_the_run(run_dir, capsys):
    runs.write_json(run_dir, "job.json", {"title": "Engineer", "company": "Zeta"})
    assert main(["job", "--run", str(run_dir)]) == exits.BLOCKED
    assert "paste" in capsys.readouterr().err.lower()


def test_a_placeholder_in_the_cv_is_not_exportable(run_dir, capsys):
    runs.write_json(run_dir, "job.json", JOB_JSON)
    main(["job", "--run", str(run_dir)])
    settled = paths.runs_dir() / read(capsys)["run"].split("/")[-1]
    runs.write_json(settled, "cv-selection.json",
                    {**SELECTION, "summary": "Engineer at [Company]."})
    assert main(["cv", "--run", str(settled)]) == exits.UNFIT


def test_a_message_over_linkedins_limit_is_refused(run_dir, capsys):
    runs.write_json(run_dir, "job.json", JOB_JSON)
    main(["job", "--run", str(run_dir)])
    settled = paths.runs_dir() / read(capsys)["run"].split("/")[-1]
    runs.write_json(settled, "outreach.json",
                    {**PLAN, "message": {"note": "word " * 200}})
    assert main(["outreach", "--run", str(settled)]) == exits.UNFIT
    assert "rejects anything over" in capsys.readouterr().out


# --- the markdown must never be a model's job -------------------------------

def test_the_markdown_is_written_even_when_the_pdf_cannot_be(run_dir, capsys, monkeypatch):
    """So there is never a gap a model would fill by writing the CV itself."""
    from job_hunter import render
    monkeypatch.setattr(render, "write_pdf", lambda *a, **k: (_ for _ in ()).throw(
        render.PdfError("no browser here")))
    runs.write_json(run_dir, "job.json", JOB_JSON)
    main(["job", "--run", str(run_dir)])
    settled = paths.runs_dir() / read(capsys)["run"].split("/")[-1]
    runs.write_json(settled, "cv-selection.json", SELECTION)

    assert main(["cv", "--run", str(settled)]) == exits.OK
    assert "Ada Lovelace" in (settled / "cv.md").read_text()


# --- nothing escapes the run directory --------------------------------------

def test_a_run_outside_the_runs_directory_is_refused(repo, capsys):
    assert main(["fit", "--run", "/etc", "--when", "before"]) == exits.BLOCKED
    assert "not a run directory" in capsys.readouterr().err


def test_a_finished_run_writes_only_inside_itself(run_dir, repo, capsys):
    before = {p for p in repo.rglob("*") if p.is_file()}
    runs.write_json(run_dir, "job.json", JOB_JSON)
    main(["job", "--run", str(run_dir)])
    settled = paths.runs_dir() / read(capsys)["run"].split("/")[-1]
    runs.write_json(settled, "cv-selection.json", SELECTION)
    main(["cv", "--run", str(settled)])
    main(["report", "--run", str(settled)])

    new = {p for p in repo.rglob("*") if p.is_file()} - before
    outside = [p for p in new if paths.runs_dir() not in p.parents
               and p.parent != paths.runs_dir()]
    assert not outside, f"wrote outside runs/: {outside}"


def test_the_log_gets_one_line_per_run(run_dir, capsys):
    runs.write_json(run_dir, "job.json", JOB_JSON)
    main(["job", "--run", str(run_dir)])
    settled = paths.runs_dir() / read(capsys)["run"].split("/")[-1]
    main(["report", "--run", str(settled)])
    main(["report", "--run", str(settled)])

    log = paths.log_path().read_text()
    assert log.count("Senior Data Engineer at Zeta") == 1, "re-running is not a new line"


# --- found by running it for real -------------------------------------------

@pytest.mark.parametrize("verb, extra", [
    ("fit", ["--when", "before"]), ("cv", []), ("letter", []),
    ("outreach", []), ("report", []),
])
def test_a_missing_input_says_what_to_run_first(repo, verb, extra, capsys):
    """A stack trace tells a person nothing they can act on."""
    empty = paths.runs_dir() / "2026-01-01-nothing-here"
    empty.mkdir(parents=True)
    assert main([verb, "--run", str(empty), *extra]) == exits.BLOCKED
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "first" in err or "missing" in err


def test_the_cv_folders_own_readme_is_not_a_cv(repo, capsys):
    (repo / paths.CV_DIR / "README.md").write_text("Put your CV here")
    main(["doctor"])
    assert read(capsys)["cv_files"] == []
