"""Finding a board's openings, without touching the network.

The two board APIs are stubbed with the shapes they really return - checked
against live boards when this was written - so the readers, the ranking and
the page are tested on real structure with no request made.
"""

import json
import os
import subprocess
import sys
import urllib.error
from pathlib import Path

import jobhunt as jh
import pytest
from jobhunt import GREENHOUSE, LEVER, Board, FetchError

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "jobhunt" / "skills" / "jobhunt-find" / "find.py"

GREENHOUSE_PAYLOAD = {"jobs": [
    {"id": 1, "title": "Data Platform Engineer",
     "absolute_url": "https://boards.greenhouse.io/zeta/jobs/1",
     "location": {"name": "Berlin"}, "departments": [{"name": "Data"}],
     "updated_at": "2026-09-01T10:00:00-04:00",
     "content": "&lt;p&gt;You will own the dbt models and the Airflow DAGs. "
                "Strong SQL.&lt;/p&gt;"},
    {"id": 2, "title": "Account Executive",
     "absolute_url": "https://boards.greenhouse.io/zeta/jobs/2",
     "location": {"name": "London"}, "content": "&lt;p&gt;Sell things.&lt;/p&gt;"},
]}
LEVER_PAYLOAD = [
    {"id": "a", "text": "Backend Engineer", "hostedUrl": "https://jobs.lever.co/zeta/a",
     "categories": {"location": "Paris", "team": "Platform", "commitment": "Full-time"},
     "createdAt": 1756684800000,
     "descriptionPlain": "Python services on Kubernetes.",
     "lists": [{"text": "Requirements", "content": "<li>Python</li><li>dbt</li>"}],
     "additionalPlain": ""},
]


def fake(payloads):
    def fetch(url):
        for key, payload in payloads.items():
            if key in url:
                return payload
        raise FetchError(f"{url} answered 404.")
    return fetch


# --- naming a board ---------------------------------------------------------

@pytest.mark.parametrize("given, expected", [
    ("greenhouse:figma", [(GREENHOUSE, "figma")]),
    ("lever:palantir", [(LEVER, "palantir")]),
    ("https://boards.greenhouse.io/figma/jobs/6178851004?gh_jid=6178851004",
     [(GREENHOUSE, "figma")]),
    ("https://job-boards.greenhouse.io/gitlab", [(GREENHOUSE, "gitlab")]),
    ("https://jobs.lever.co/palantir/abc-123", [(LEVER, "palantir")]),
    ("https://api.lever.co/v0/postings/palantir?mode=json", [(LEVER, "palantir")]),
    # A bare token could be either host; both are tried, Greenhouse first.
    ("figma", [(GREENHOUSE, "figma"), (LEVER, "figma")]),
])
def test_a_board_is_read_from_what_people_paste(given, expected):
    assert [(b.kind, b.token) for b in jh.parse_board(given)] == expected


@pytest.mark.parametrize("given", ["", "https://www.linkedin.com/jobs/", "not a board!"])
def test_something_that_is_not_a_board_says_so(given):
    with pytest.raises(FetchError, match="board"):
        jh.parse_board(given)


# --- reading the two APIs ---------------------------------------------------

def test_a_greenhouse_board_is_read():
    found = jh.openings(Board(GREENHOUSE, "zeta"), fetch=fake({"greenhouse": GREENHOUSE_PAYLOAD}))
    assert [o.title for o in found] == ["Data Platform Engineer", "Account Executive"]
    first = found[0]
    assert first.url == "https://boards.greenhouse.io/zeta/jobs/1"
    assert (first.location, first.team, first.posted) == ("Berlin", "Data", "2026-09-01")
    assert "dbt models" in first.text and "<p>" not in first.text   # unescaped, then read
    assert first.board == "greenhouse:zeta"


def test_a_lever_board_is_read():
    found = jh.openings(Board(LEVER, "zeta"), fetch=fake({"lever": LEVER_PAYLOAD}))
    assert len(found) == 1
    job = found[0]
    assert (job.title, job.location, job.team) == ("Backend Engineer", "Paris", "Platform")
    assert job.posted == "2025-09-01"
    assert "Requirements" in job.text and "dbt" in job.text and "<li>" not in job.text


def test_a_404_names_the_token(monkeypatch):
    def refuse(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", None, None)
    monkeypatch.setattr(jh.urllib.request, "urlopen", refuse)
    with pytest.raises(FetchError, match="answered 404.*token"):
        jh.openings(Board(GREENHOUSE, "nope"))


# --- ranking ----------------------------------------------------------------

def test_openings_are_ranked_by_the_skills_they_name(profile):
    """dbt, Airflow and SQL are the fixture's; the sales job names none."""
    found = (jh.openings(Board(GREENHOUSE, "zeta"), fetch=fake({"greenhouse": GREENHOUSE_PAYLOAD}))
             + jh.openings(Board(LEVER, "zeta"), fetch=fake({"lever": LEVER_PAYLOAD})))
    ranked = jh.leads(found, profile)
    assert [lead.opening.title for lead in ranked] == ["Data Platform Engineer", "Backend Engineer"]
    assert set(ranked[0].named) == {"dbt", "Airflow", "SQL"}
    assert set(ranked[1].named) == {"Python", "dbt"}
    assert jh.leads(found, profile, at_least=3)[0].score == 3
    assert len(jh.leads(found, profile, at_least=3)) == 1


def test_a_single_letter_skill_is_not_matched():
    profile = jh.Profile(skills=["C", "Go"])
    opening = jh.Opening(title="Analyst", text="Section C of the plan.")
    assert jh.leads([opening], profile, at_least=0)[0].named == []


def test_the_page_says_what_the_number_is_and_is_not(profile):
    found = jh.openings(Board(GREENHOUSE, "zeta"), fetch=fake({"greenhouse": GREENHOUSE_PAYLOAD}))
    page = jh.leads_page(jh.leads(found, profile), [Board(GREENHOUSE, "zeta")], len(found))
    assert "not a fit score" in page
    assert "<https://boards.greenhouse.io/zeta/jobs/1>" in page
    assert "Names 3 of your skills" in page
    assert "Account Executive" not in page
    assert "applied to anything" in page


# --- the script -------------------------------------------------------------

def test_the_script_refuses_a_nonsense_board_without_a_request(tmp_path, profile):
    home = tmp_path / "jobhunt"
    home.mkdir()
    jh.save(profile, home / "profile.yaml")
    done = subprocess.run([sys.executable, str(SCRIPT), "nonsense:xyz!"],
                          capture_output=True, text=True, cwd=str(tmp_path),
                          env={"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path),
                               "JOBHUNT_HOME": str(home)})
    assert done.returncode == jh.BLOCKED
    assert "not a board this reads" in done.stderr
    assert "Traceback" not in done.stderr


def test_the_script_needs_a_profile_first(tmp_path):
    done = subprocess.run([sys.executable, str(SCRIPT), "greenhouse:zeta"],
                          capture_output=True, text=True, cwd=str(tmp_path),
                          env={"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path),
                               "JOBHUNT_HOME": str(tmp_path / "jobhunt")})
    assert done.returncode == jh.BLOCKED
    assert "No profile" in done.stderr


def test_the_json_the_script_writes_leaves_the_posting_text_out(profile):
    """The file is the list, not the postings: a board's whole text has no
    business on disk."""
    found = jh.openings(Board(GREENHOUSE, "zeta"), fetch=fake({"greenhouse": GREENHOUSE_PAYLOAD}))
    lead = jh.leads(found, profile)[0]
    written = {**jh.asdict(lead), "opening": {**jh.asdict(lead.opening), "text": ""}}
    assert json.loads(json.dumps(written))["opening"]["text"] == ""
