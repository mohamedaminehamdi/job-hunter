"""Finding a board's openings, without touching the network.

The two board APIs are stubbed with the shapes they really return - checked
against live boards when this was written - so the readers, the ranking and
the page are tested on real structure with no request made.
"""

import http.client
import importlib.util
import io
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
    {"id": 1, "title": "Data Platform Engineer", "company_name": "Zeta GmbH",
     "absolute_url": "https://boards.greenhouse.io/zeta/jobs/1",
     "location": {"name": "Berlin"}, "departments": [{"name": "Data"}],
     "first_published": "2026-07-15T09:00:00-04:00",
     "updated_at": "2026-09-01T10:00:00-04:00",
     "content": "&lt;p&gt;You will own the dbt models and the Airflow DAGs. "
                "Strong SQL.&lt;/p&gt;"},
    {"id": 2, "title": "Account Executive",
     "absolute_url": "https://boards.greenhouse.io/zeta/jobs/2",
     "updated_at": "2026-08-20T10:00:00-04:00",
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
    # The embed script's path says "embed"; the board is the ?for= parameter.
    ("https://boards.greenhouse.io/embed/job_board?for=figma", [(GREENHOUSE, "figma")]),
    ("boards.greenhouse.io/embed/job_app?token=6178851004&for=figma", [(GREENHOUSE, "figma")]),
    # A bare token could be either host; both are tried, Greenhouse first.
    ("figma", [(GREENHOUSE, "figma"), (LEVER, "figma")]),
])
def test_a_board_is_read_from_what_people_paste(given, expected):
    assert [(b.kind, b.token) for b in jh.parse_board(given)] == expected


@pytest.mark.parametrize("given, api", [
    ("https://job-boards.eu.greenhouse.io/acme/jobs/1",
     "https://boards.eu.greenhouse.io/v1/boards/acme/jobs?content=true"),
    ("https://jobs.eu.lever.co/acme/abc-123", "https://api.eu.lever.co/v0/postings/acme?mode=json"),
    ("https://job-boards.greenhouse.io/acme",
     "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true"),
    ("lever:acme", "https://api.lever.co/v0/postings/acme?mode=json"),
])
def test_an_eu_board_is_asked_on_the_eu_api(given, api):
    [board] = jh.parse_board(given)
    assert board.api == api


@pytest.mark.parametrize("given", ["", "https://www.linkedin.com/jobs/", "not a board!",
                                   "https://boards.greenhouse.io/embed/job_board"])
def test_something_that_is_not_a_board_says_so(given):
    with pytest.raises(FetchError, match="board"):
        jh.parse_board(given)


# --- reading the two APIs ---------------------------------------------------

def test_a_greenhouse_board_is_read():
    found = jh.openings(Board(GREENHOUSE, "zeta"), fetch=fake({"greenhouse": GREENHOUSE_PAYLOAD}))
    assert [o.title for o in found] == ["Data Platform Engineer", "Account Executive"]
    first, second = found
    assert first.url == "https://boards.greenhouse.io/zeta/jobs/1"
    # first_published is when it went up; updated_at only when nothing else says.
    assert (first.location, first.team, first.posted) == ("Berlin", "Data", "2026-07-15")
    assert second.posted == "2026-08-20"
    assert (first.company, second.company) == ("Zeta GmbH", "Zeta")
    assert "dbt models" in first.text and "<p>" not in first.text   # unescaped, then read
    assert first.board == "greenhouse:zeta"


def test_a_lever_board_is_read():
    found = jh.openings(Board(LEVER, "zeta"), fetch=fake({"lever": LEVER_PAYLOAD}))
    assert len(found) == 1
    job = found[0]
    assert (job.title, job.location, job.team) == ("Backend Engineer", "Paris", "Platform")
    assert job.posted == "2025-09-01"
    assert job.company == "Zeta"
    assert "Requirements" in job.text and "dbt" in job.text and "<li>" not in job.text


def test_a_lever_company_is_its_token_as_a_name():
    assert Board(LEVER, "acme-corp_eu").company == "Acme Corp Eu"


@pytest.mark.parametrize("created", [True, 10 ** 30, "2025-09-01"])
def test_a_lever_date_that_is_not_a_timestamp_is_left_out(created):
    [job] = jh.openings(Board(LEVER, "zeta"),
                        fetch=lambda url: [{"text": "Engineer", "createdAt": created}])
    assert job.posted == ""


# --- what the network can do wrong -------------------------------------------

def answering(monkeypatch, body=b"", error=None):
    """Stand in for urlopen; returns the requests it was handed."""
    seen = []

    def urlopen(request, timeout):
        seen.append(request)
        if error is not None:
            raise error
        return io.BytesIO(body)
    monkeypatch.setattr(jh.urllib.request, "urlopen", urlopen)
    return seen


def test_the_board_apis_are_asked_as_jobhunt_not_as_chrome(monkeypatch):
    seen = answering(monkeypatch, body=json.dumps(GREENHOUSE_PAYLOAD).encode())
    assert len(jh.openings(Board(GREENHOUSE, "zeta"))) == 2
    agent = seen[0].get_header("User-agent")
    assert agent == jh.API_USER_AGENT and "Chrome" not in agent


@pytest.mark.parametrize("code, says, not_says", [
    (404, "Check the board token", None),
    (400, "Check the board token", None),
    (429, "limiting requests", "token"),
    (503, "failed on its side", "token"),
])
def test_an_http_error_says_what_it_means(monkeypatch, code, says, not_says):
    answering(monkeypatch, error=urllib.error.HTTPError("https://x", code, "no", None, None))
    with pytest.raises(FetchError, match=f"answered {code}") as raised:
        jh.openings(Board(GREENHOUSE, "zeta"))
    assert says in str(raised.value)
    assert not_says is None or not_says not in str(raised.value)


@pytest.mark.parametrize("error, says", [
    (urllib.error.URLError("nodename nor servname provided"), "Could not reach"),
    (http.client.IncompleteRead(b"{\"jobs\": ["), "broke off mid-answer"),
])
def test_a_connection_that_fails_says_so(monkeypatch, error, says):
    answering(monkeypatch, error=error)
    with pytest.raises(FetchError, match=says):
        jh.openings(Board(GREENHOUSE, "zeta"))


def test_a_page_that_is_not_json_says_so(monkeypatch):
    answering(monkeypatch, body=b"<html><body>Maintenance</body></html>")
    with pytest.raises(FetchError, match="did not answer with JSON"):
        jh.openings(Board(GREENHOUSE, "zeta"))


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


BOTH = {"greenhouse": GREENHOUSE_PAYLOAD, "lever": LEVER_PAYLOAD}


def find(monkeypatch, capsys, tmp_path, profile, fetch, *argv):
    """find.py's work(), run in this process so the boards can be stubbed.

    Returns the exit code, the JSON it emitted, what it told the person, and
    the folder it writes to.
    """
    home = tmp_path / "jobhunt"
    home.mkdir(exist_ok=True)
    jh.save(profile, home / "profile.yaml")
    monkeypatch.setenv("JOBHUNT_HOME", str(home))
    monkeypatch.setattr(jh, "fetch_json", fetch)
    monkeypatch.setattr(sys, "path", list(sys.path))   # the script prepends its lib/
    spec = importlib.util.spec_from_file_location("find_script", SCRIPT)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    assert script.jh is jh   # the stub reaches the script, not a second copy
    code = jh.run_cli(script.work, list(argv))
    out, err = capsys.readouterr()
    return code, (json.loads(out) if out.strip() else None), err, home / "found"


def test_the_script_writes_the_page_and_the_list_beside_it(monkeypatch, capsys, tmp_path,
                                                           profile):
    code, emitted, err, where = find(monkeypatch, capsys, tmp_path, profile, fake(BOTH),
                                     "greenhouse:zeta", "lever:zeta")
    assert code == jh.OK
    stem = f"{jh.today()}-zeta-zeta"
    assert sorted(p.name for p in where.iterdir()) == [f"{stem}.json", f"{stem}.md"]
    page = (where / f"{stem}.md").read_text(encoding="utf-8")
    assert page.startswith("# Openings worth reading - greenhouse:zeta, lever:zeta")
    assert page in err   # what it wrote is what it showed
    assert emitted["boards"] == ["greenhouse:zeta", "lever:zeta"]
    assert (emitted["openings"], emitted["matched"], emitted["listed"]) == (3, 2, 2)
    assert emitted["page"] == str(where / f"{stem}.md")


def test_the_json_the_script_writes_leaves_the_posting_text_out(monkeypatch, capsys, tmp_path,
                                                                profile):
    """The file is the list, not the postings: a board's whole text has no
    business on disk."""
    _, _, _, where = find(monkeypatch, capsys, tmp_path, profile, fake(BOTH),
                          "greenhouse:zeta", "lever:zeta")
    [written] = where.glob("*.json")
    listed = json.loads(written.read_text(encoding="utf-8"))
    assert [lead["opening"]["title"] for lead in listed] == ["Data Platform Engineer",
                                                             "Backend Engineer"]
    assert set(listed[0]["named"]) == {"dbt", "Airflow", "SQL"}
    assert all(lead["opening"]["text"] == "" for lead in listed)
    assert "dbt models" not in written.read_text(encoding="utf-8")


@pytest.mark.parametrize("flags, header, titles", [
    ((), "2 of 3 openings name at least 1 of your listed skills, ranked by how many.",
     ["Data Platform Engineer", "Backend Engineer"]),
    # The count is what matched, not what the limit let onto the page.
    (("--limit", "1"), "2 of 3 openings name at least 1 of your listed skills; "
     "showing the top 1, ranked by how many.", ["Data Platform Engineer"]),
    (("--min", "3"), "1 of 3 openings name at least 3 of your listed skills, ranked",
     ["Data Platform Engineer"]),
    (("--title", "ENGINEER"), "2 of 2 openings name at least 1",
     ["Data Platform Engineer", "Backend Engineer"]),
])
def test_the_header_says_how_many_matched_and_how_many_are_shown(
        monkeypatch, capsys, tmp_path, profile, flags, header, titles):
    code, emitted, _, where = find(monkeypatch, capsys, tmp_path, profile, fake(BOTH),
                                   "greenhouse:zeta", "lever:zeta", *flags)
    assert code == jh.OK
    [page] = where.glob("*.md")
    body = page.read_text(encoding="utf-8")
    assert header in body
    assert [line[3:].split(" - ")[0] for line in body.splitlines()
            if line.startswith("## ")] == titles
    assert emitted["listed"] == len(titles)


def test_a_bare_token_falls_through_to_the_host_that_answers(monkeypatch, capsys, tmp_path,
                                                             profile):
    code, emitted, _, where = find(monkeypatch, capsys, tmp_path, profile,
                                   fake({"lever": LEVER_PAYLOAD}), "zeta")
    assert code == jh.OK
    assert emitted["boards"] == ["lever:zeta"]
    assert (where / f"{jh.today()}-zeta.md").exists()


def test_a_bare_token_on_neither_host_says_why_for_both(monkeypatch, capsys, tmp_path, profile):
    def fetch(url):
        if "greenhouse" in url:
            raise FetchError(f"{url} answered 503. The board's API failed on its side.")
        raise FetchError(f"{url} answered 404. Check the board token.")
    code, emitted, err, where = find(monkeypatch, capsys, tmp_path, profile, fetch, "zeta")
    assert code == jh.BLOCKED and emitted is None
    assert "greenhouse:zeta: " in err and "answered 503" in err
    assert "lever:zeta: " in err and "answered 404" in err
    assert "Traceback" not in err
    assert not where.exists()


def test_a_board_that_answers_html_stops_the_script_with_a_sentence(monkeypatch, capsys,
                                                                    tmp_path, profile):
    answering(monkeypatch, body=b"<!doctype html><title>Down for maintenance</title>")
    code, _, err, _ = find(monkeypatch, capsys, tmp_path, profile, jh.fetch_json,
                           "greenhouse:zeta")
    assert code == jh.BLOCKED
    assert "did not answer with JSON" in err
