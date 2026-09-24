"""One whole application, through the scripts, as subprocesses.

Everything else tests the library. This runs the eight scripts the way an agent
runs them - argv in, JSON on stdout, an exit code - because the seams between
them are where a refactor breaks something no unit test is watching.

Nothing here touches the network: the posting arrives as pasted text, which is
a fully supported path and the one a login wall forces anyway.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import jobhunt as jh
import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins" / "jobhunt" / "skills"

#: Long enough to pass the "is this actually a posting" check, because that
#: check is real and a fixture that ducks it tests nothing.
POSTING = """Senior Data Engineer at Zeta

Zeta runs a data platform for logistics customers across Europe. The team owns
ingestion, modelling and the warehouse that the rest of the company reports
from, and you would own the ingestion pipelines end to end and share the
on-call rota for the platform with four other engineers.

What you would do

- Own the ingestion pipelines that bring customer shipment data into the
  warehouse, and the alerting that tells us when they are wrong.
- Work with the analytics team on the models they build on top of it.
- Take part in the on-call rota for the data platform.

Requirements

- Strong Python
- Strong SQL
- Experience with dbt
- 3+ years in data engineering

Nice to have

- Kafka
- Terraform

We are a remote-first company with an office in Berlin. We offer a learning
budget, and we will pay to relocate you if you would rather be in the office.
"""

JOB = {
    "title": "Senior Data Engineer", "company": "Zeta", "location": "Berlin",
    "workplace": "hybrid", "language": "en",
    "description": "Zeta runs a data platform for logistics customers. You would "
                   "own the ingestion pipelines and share the on-call rota.",
    "requirements": ["Strong Python", "Strong SQL", "Experience with dbt",
                     "3+ years in data engineering"],
    "nice_to_have": ["Kafka", "Terraform"],
    "keywords": ["Python", "SQL", "dbt"],
}

SELECTION = {
    "summary": "Data engineer who builds pipelines that stay up.",
    "roles": [{"index": 0, "bullets": ["Cut ETL runtime by 35% by rewriting the "
                                       "dbt models."]}],
    "projects": [], "skills": ["Python", "SQL", "dbt"],
}

LETTER = {"greeting": "Dear Zeta team,",
          "paragraphs": ["I cut ETL runtime by 35% by rewriting the dbt models "
                         "at Acme, and would like to do the same at Zeta."],
          "closing": "Kind regards,"}

OUTREACH = {"targets": [{"tier": "peer", "title": "Data Engineer",
                         "why": "Would be my colleague."}],
            "message": {"subject": "dbt at Zeta",
                        "note": "I rewrote the dbt models at Acme. How does Zeta "
                                "run its warehouse day to day?",
                        "inmail": "I rewrote the dbt models at Acme and cut ETL "
                                  "runtime by 35%. How does Zeta split ownership "
                                  "of the warehouse?"}}


def script(skill):
    return next(iter(sorted((SKILLS / skill).glob("*.py"))))


@pytest.fixture
def work(tmp_path, profile):
    """A workspace with a saved profile, the way a second run finds one."""
    home = tmp_path / "work"
    (home / "jobhunt").mkdir(parents=True)
    jh.save(profile, home / "jobhunt" / "profile.yaml")
    return home


def run(skill, *args, work=None, check=True):
    done = subprocess.run(
        [sys.executable, str(script(skill)), *[str(a) for a in args]],
        capture_output=True, text=True, cwd=str(work),
        env={"PATH": os.environ.get("PATH", ""), "HOME": str(work),
             "JOBHUNT_HOME": str(Path(work) / "jobhunt")})
    if check:
        assert done.returncode == jh.OK, f"{skill} exited {done.returncode}\n{done.stderr}"
    return done


def emitted(done):
    """The JSON line a script prints for the agent to read."""
    for line in reversed(done.stdout.splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON on stdout:\n{done.stdout}\n{done.stderr}")


def write(work, name, payload):
    path = Path(work) / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# --- the whole thing --------------------------------------------------------

def test_one_application_start_to_finish(work):
    posting = Path(work) / "posting.txt"
    posting.write_text(POSTING, encoding="utf-8")

    got = emitted(run("jobhunt-posting", "--text", posting,
                      "https://zeta.example/jobs/1", work=work))
    run_dir = Path(got["run"])
    assert (run_dir / "page.txt").exists()

    got = emitted(run("jobhunt-posting", "--parse", write(work, "job.json", JOB),
                      "--run", run_dir, work=work))
    run_dir = Path(got["run"])
    assert run_dir.name.endswith("zeta-senior-data-engineer")
    assert got["requirements"] == 4

    before = emitted(run("jobhunt-fit", "--run", run_dir, "--when", "before",
                         work=work))
    assert before["evidenced"] >= 1
    assert (run_dir / "fit-before.md").exists()

    run("jobhunt-tailor", write(work, "sel.json", SELECTION), "--run", run_dir,
        work=work)
    assert (run_dir / "cv.yaml").exists()

    after = emitted(run("jobhunt-fit", "--run", run_dir, "--when", "after",
                        work=work))
    # The property the whole design turns on: rewriting the CV cannot change
    # what the profile can back.
    assert after["evidenced"] == before["evidenced"]
    assert after["shown"] >= before["shown"]

    run("jobhunt-letter", write(work, "letter.json", LETTER), "--run", run_dir,
        work=work)
    assert (run_dir / "letter.yaml").exists()

    for document in ("cv.yaml", "letter.yaml"):
        got = emitted(run("jobhunt-pdf", run_dir / document, work=work))
        assert Path(got["markdown"]).exists()

    run("jobhunt-outreach", write(work, "out.json", OUTREACH), "--run", run_dir,
        work=work)
    assert (run_dir / "outreach.md").exists()

    got = emitted(run("jobhunt-critique", "--run", run_dir, work=work))
    assert got["has_cv"] and got["has_letter"]

    log = (Path(work) / "jobhunt" / "runs" / "log.md").read_text()
    assert "Senior Data Engineer at Zeta" in log


# --- the refusals -----------------------------------------------------------

def test_what_we_observed_beats_what_the_model_wrote(work):
    posting = Path(work) / "p.txt"
    posting.write_text(POSTING, encoding="utf-8")
    got = emitted(run("jobhunt-posting", "--text", posting,
                      "https://real.example/jobs/1", work=work))
    lying = dict(JOB, url="https://spam.example")
    got = emitted(run("jobhunt-posting", "--parse", write(work, "j.json", lying),
                      "--run", got["run"], work=work))
    saved = jh.load(jh.Job, Path(got["run"]) / "job.yaml")
    assert saved.url == "https://real.example/jobs/1"


def test_a_posting_too_thin_to_use_stops_the_run(work):
    thin = Path(work) / "thin.txt"
    thin.write_text("Data Engineer. Apply now.", encoding="utf-8")
    done = run("jobhunt-posting", "--text", thin, "https://x.example/1",
               work=work, check=False)
    assert done.returncode == jh.BLOCKED
    assert "characters came back" in done.stderr or "Paste" in done.stderr


@pytest.mark.parametrize("skill, name", [
    ("jobhunt-posting", "job.json"), ("jobhunt-tailor", "sel.json"),
    ("jobhunt-letter", "letter.json"), ("jobhunt-outreach", "out.json"),
])
def test_unreadable_json_says_so_and_does_not_traceback(work, skill, name):
    broken = Path(work) / name
    broken.write_text("I can't help with that.", encoding="utf-8")
    args = ["--parse", broken, "--run", "x"] if skill == "jobhunt-posting" \
        else [broken, "--run", "x"]
    done = run(skill, *args, work=work, check=False)
    assert done.returncode in (jh.UNREADABLE, jh.BLOCKED)
    assert "Traceback" not in done.stderr


def test_a_run_outside_the_runs_directory_is_refused(work):
    done = run("jobhunt-fit", "--run", "/etc", "--when", "before",
               work=work, check=False)
    assert done.returncode == jh.BLOCKED
    assert "not a run directory" in done.stderr


def test_a_placeholder_in_the_cv_is_not_exportable(work, profile):
    run_dir = Path(work) / "jobhunt" / "runs" / "2026-01-01-zeta"
    run_dir.mkdir(parents=True)
    jh.save(jh.build(jh.Job, JOB), run_dir / "job.yaml")
    document = jh.tailor(profile, jh.build(jh.Job, JOB), SELECTION)
    document.summary = "Data engineer at [Company Name]."
    jh.save(document, run_dir / "cv.yaml")

    done = run("jobhunt-pdf", run_dir / "cv.yaml", work=work, check=False)
    assert done.returncode == jh.UNFIT
    assert "placeholder" in done.stderr.lower()
    assert not (run_dir / "cv.pdf").exists()


def test_a_message_over_linkedins_limit_is_refused(work):
    run_dir = Path(work) / "jobhunt" / "runs" / "2026-01-01-zeta"
    run_dir.mkdir(parents=True)
    jh.save(jh.build(jh.Job, JOB), run_dir / "job.yaml")
    long = dict(OUTREACH)
    long["message"] = dict(OUTREACH["message"], note="x " * 200)
    done = run("jobhunt-outreach", write(work, "o.json", long), "--run", run_dir,
               work=work, check=False)
    assert done.returncode == jh.UNFIT
    assert "LinkedIn rejects" in done.stderr


def test_a_missing_input_says_what_to_do_first(work):
    run_dir = Path(work) / "jobhunt" / "runs" / "2026-01-01-zeta"
    run_dir.mkdir(parents=True)
    done = run("jobhunt-fit", "--run", run_dir, "--when", "before",
               work=work, check=False)
    assert done.returncode == jh.BLOCKED
    assert "read the posting first" in done.stderr


def test_a_run_writes_only_inside_itself(work):
    """Nothing lands outside the run except the one line in the log."""
    posting = Path(work) / "p.txt"
    posting.write_text(POSTING, encoding="utf-8")
    got = emitted(run("jobhunt-posting", "--text", posting, "https://z.example/1",
                      work=work))
    got = emitted(run("jobhunt-posting", "--parse", write(work, "j.json", JOB),
                      "--run", got["run"], work=work))
    run_dir = Path(got["run"])
    run("jobhunt-tailor", write(work, "s.json", SELECTION), "--run", run_dir,
        work=work)

    inside = {p for p in (Path(work) / "jobhunt").rglob("*") if p.is_file()}
    allowed = {Path(work) / "jobhunt" / "profile.yaml",
               Path(work) / "jobhunt" / "runs" / "log.md"}
    for path in inside - allowed:
        assert run_dir in path.parents, f"{path} is outside the run"
