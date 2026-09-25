"""The pieces that exist only because this file has to install by being copied.

Everything here replaced a dependency - pydantic, Jinja, playwright, pypdf -
and each replacement carries a risk the library was handling for us. These are
the tests for that risk, not for the behaviour, which is covered where the
behaviour lives.
"""

import zipfile

import jobhunt as jh
import pytest

POISON = '<script>alert("x")</script>"\'&'
STR_FIELDS = ("name surname headline email phone city country github linkedin "
              "website").split()


@pytest.fixture
def poisoned():
    """A profile whose every string field is an injection attempt."""
    return jh.Profile(
        personal=jh.Personal(**{f: POISON for f in STR_FIELDS}),
        summary=POISON, skills=[POISON],
        experience=[jh.Role(position=POISON, company=POISON, start=POISON,
                            end=POISON, location=POISON, industry=POISON,
                            bullets=[POISON], skills=[POISON])],
        education=[jh.Education(level=POISON, institution=POISON,
                                field_of_study=POISON, start=POISON, end=POISON,
                                grade=POISON, location=POISON, courses=[POISON])],
        projects=[jh.Project(name=POISON, description=POISON, link=POISON,
                             tech=[POISON])],
        certifications=[jh.Certification(name=POISON, issuer=POISON, year=POISON,
                                         description=POISON)],
        languages=[jh.Language(name=POISON, level=POISON)],
    )


# --- escaping: Jinja did this for us, now it is done by hand ---------------

@pytest.mark.parametrize("theme", [jh.NEUTRAL, jh.CLASSIC, jh.branded("#7b2ff7")])
def test_no_field_of_a_cv_can_inject_markup(poisoned, theme):
    page = jh.cv_html(poisoned, theme)
    assert "<script>" not in page
    assert 'alert("x")' not in page
    assert "&lt;script&gt;" in page  # it is there, escaped


def test_no_field_of_a_letter_can_inject_markup(poisoned):
    letter = jh.CoverLetter(personal=poisoned.personal, greeting=POISON,
                            paragraphs=[POISON], closing=POISON, signature=POISON,
                            written_on=POISON, language=POISON, company=POISON,
                            role=POISON)
    page = jh.letter_html(letter)
    assert "<script>" not in page and 'alert("x")' not in page


def test_a_link_cannot_break_out_of_its_attribute(poisoned):
    """The one place an escaped value sits inside quotes rather than between tags."""
    page = jh.cv_html(poisoned)
    for chunk in page.split('href="')[1:]:
        assert "<" not in chunk.split('"')[0]


def test_the_accent_reaches_css_only_as_a_hex_colour():
    """It is interpolated into a stylesheet, so it is checked, not escaped."""
    attack = jh.branded("#fff;} body{display:none} .x{color:#000")
    assert attack.accent == jh.NEUTRAL_ACCENT
    assert "display:none" not in jh.cv_html(jh.Profile(), attack)


def test_the_font_stack_keeps_its_quotes():
    """Escaping it would turn the stack into &#34; and drop the page to serif."""
    assert '"Segoe UI"' in jh.cv_html(jh.Profile())


# --- coercion: pydantic did this for us ------------------------------------

def test_clone_is_deep_so_a_copy_does_not_share_its_lists():
    """model_copy(deep=True). A shallow copy here silently edits the original."""
    original = jh.Profile(skills=["Python"],
                          experience=[jh.Role(company="Acme", bullets=["One."])])
    copied = jh.clone(original)
    copied.skills.append("Go")
    copied.experience[0].bullets.append("Two.")
    assert original.skills == ["Python"]
    assert original.experience[0].bullets == ["One."]


def test_clone_applies_changes():
    assert jh.clone(jh.Job(title="A"), title="B").title == "B"


def test_build_never_raises_whatever_it_is_given():
    for junk in (None, [], "text", 42, {"experience": object()},
                 {"personal": "not a mapping"}, {"skills": {"a": "b"}}):
        assert isinstance(jh.build(jh.Profile, junk), jh.Profile)


def test_a_colour_is_coerced_even_on_direct_construction():
    """It reaches a stylesheet, so it cannot wait for build() to clean it."""
    assert jh.Job(brand_color="red").brand_color == ""
    assert jh.Job(brand_color="#ABC").brand_color == "#aabbcc"


# --- reading a CV: pypdf and python-docx did this for us -------------------

def _docx(path, paragraphs):
    """The smallest thing Word will still call a .docx."""
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml",
                         f'<?xml version="1.0"?><w:document xmlns:w="{W}">'
                         f"<w:body>{body}</w:body></w:document>")
    return path


def test_a_docx_is_read_without_a_library(tmp_path):
    path = _docx(tmp_path / "cv.docx", ["Ada Lovelace", "", "Wrote note G."])
    assert jh.read_cv_text(path) == "Ada Lovelace\nWrote note G."


def test_a_broken_docx_says_so(tmp_path):
    bad = tmp_path / "cv.docx"
    bad.write_text("not a zip")
    with pytest.raises(jh.IntakeError, match="Could not read"):
        jh.read_cv_text(bad)


def test_a_pdf_is_handed_back_to_the_agent(tmp_path):
    """Reading a CV layout is judgement, and the agent can open a PDF."""
    pdf = tmp_path / "cv.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    with pytest.raises(jh.IntakeError, match="Read it yourself"):
        jh.read_cv_text(pdf)


def test_plain_text_is_read_as_it_is(tmp_path):
    path = tmp_path / "cv.md"
    path.write_text("# Ada\n\nWrote note G.\n", encoding="utf-8")
    assert "Wrote note G." in jh.read_cv_text(path)


# --- the workspace ---------------------------------------------------------

def test_the_workspace_is_one_directory_not_three(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBHUNT_HOME", str(tmp_path / "jobhunt"))
    for path in (jh.cv_dir(), jh.runs_dir(), jh.profile_path()):
        assert path.parent == tmp_path / "jobhunt" or path == tmp_path / "jobhunt"


def test_a_parent_workspace_is_found_from_a_subfolder(tmp_path, monkeypatch):
    """Run from anywhere inside your job search and it still finds your profile."""
    monkeypatch.delenv("JOBHUNT_HOME", raising=False)
    work = tmp_path / "jobhunt"
    work.mkdir()
    (work / "profile.yaml").write_text("personal:\n  name: Ada\n")
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)
    assert jh.home() == work


def test_with_no_workspace_anywhere_it_uses_the_current_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("JOBHUNT_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    assert jh.home() == tmp_path.resolve() / "jobhunt"


def test_a_run_outside_the_runs_directory_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBHUNT_HOME", str(tmp_path))
    with pytest.raises(ValueError, match="not a run directory"):
        jh.run_dir("/etc")
    with pytest.raises(ValueError, match="not a run directory"):
        jh.run_dir("../../etc/passwd")


def test_a_run_is_addressed_by_name(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBHUNT_HOME", str(tmp_path))
    assert jh.run_dir("2026-09-24-acme") == (tmp_path / "runs" / "2026-09-24-acme").resolve()


def test_save_is_atomic(tmp_path):
    """An interrupted write must not leave half a profile where a whole one was."""
    path = tmp_path / "profile.yaml"
    jh.save(jh.Profile(personal=jh.Personal(name="Ada")), path)
    assert not list(tmp_path.glob("*.tmp"))
    assert jh.load(jh.Profile, path).personal.name == "Ada"


# --- the PDF: playwright did this for us -----------------------------------

needs_browser = pytest.mark.skipif(jh.find_browser() is None,
                                   reason="no Chromium-family browser on this machine")


@needs_browser
def test_a_pdf_comes_out_of_the_browser_already_installed(tmp_path):
    import re
    path = jh.write_pdf(jh.cv_html(jh.Profile(personal=jh.Personal(name="Ada"))),
                        tmp_path / "cv.pdf")
    raw = path.read_bytes()
    assert raw.startswith(b"%PDF")
    # A4 at 72dpi, taken from the stylesheet's @page rule rather than a default.
    boxes = {tuple(round(float(n)) for n in box.split())
             for box in re.findall(rb"/MediaBox\s*\[([^\]]+)\]", raw)}
    assert boxes == {(0, 0, 595, 842)}, boxes


@needs_browser
def test_the_browser_does_not_hold_the_run_open(tmp_path, monkeypatch):
    """Chrome lingers after writing the PDF; it does not exit on its own. Wait
    on it and a 2-second render becomes a hang.

    This used to assert a wall clock bound, which measured the machine rather
    than the code and flaked on a loaded one. The regression is specifically an
    unbounded `wait()`, so that is what is asserted: every wait the render does
    carries a timeout, and none of them is long.
    """
    import subprocess
    waits = []
    real = subprocess.Popen.wait

    def spy(self, timeout=None):
        waits.append(timeout)
        return real(self, timeout=timeout)

    monkeypatch.setattr(subprocess.Popen, "wait", spy)
    jh.write_pdf("<p>hi</p>", tmp_path / "x.pdf")
    assert all(t is not None for t in waits), \
        f"an unbounded wait on the browser: {waits}"
    assert all(t <= 5 for t in waits if t is not None), waits


def test_no_browser_says_the_markdown_was_still_written(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_HUNTER_BROWSER", "/nonexistent/browser")
    with pytest.raises(jh.PdfError, match="markdown version was still written"):
        jh.write_pdf("<p>hi</p>", tmp_path / "x.pdf")


# --- it has to run where people are ----------------------------------------

#: Every module `core/jobhunt.py` is allowed to import. Listed rather than
#: checked against sys.stdlib_module_names, which is itself 3.10+, and because
#: an allowlist says what the dependency budget *is* - adding to it should be a
#: decision someone makes, not something a test waves through.
ALLOWED = {
    "__future__", "ast", "copy", "dataclasses", "datetime", "hashlib", "html",
    "json", "os", "pathlib", "re", "shutil", "subprocess", "sys", "tempfile",
    "time", "xml", "zipfile",
}


def test_this_file_imports_nothing_that_is_not_on_the_list():
    """Zero install is the whole premise: one file, copied, that runs."""
    import ast
    import pathlib
    imported = set()
    for node in ast.walk(ast.parse(pathlib.Path(jh.__file__).read_text("utf-8"))):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= ALLOWED, f"new dependency: {imported - ALLOWED}"


#: Names that exist on newer Pythons and not on 3.9. Checked through the AST,
#: not by searching the text, so the comment explaining the rule does not trip
#: the rule.
TOO_NEW = {"StrEnum", "removeprefix", "removesuffix", "batched", "pairwise"}


def test_it_runs_on_the_python_macos_ships():
    """3.9.6, which is what a friend on a fresh Mac has and will not upgrade."""
    import ast
    import pathlib
    tree = ast.parse(pathlib.Path(jh.__file__).read_text("utf-8"),
                     feature_version=(3, 9))  # raises on a match statement

    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            used.add(node.attr)
            # datetime.UTC is 3.11; timezone.utc is what works everywhere
            if node.attr == "UTC" and getattr(node.value, "id", "") == "datetime":
                used.add("datetime.UTC")
        elif isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.ImportFrom) and node.module == "datetime":
            # `from datetime import UTC` is the same 3.11 name by another route,
            # and it is the one ruff's UP017 reaches for.
            used |= {f"datetime.{a.name}" for a in node.names if a.name == "UTC"}
    banned = used & (TOO_NEW | {"datetime.UTC"})
    assert not banned, f"needs a Python newer than 3.9: {sorted(banned)}"


# --- what run_cli turns an exception into ----------------------------------

def test_every_error_the_library_raises_is_one_run_cli_handles():
    """An omission here does not fail loudly - it prints a traceback where a
    sentence should be. FetchError was missing, so a login wall, the most
    ordinary failure there is, came out as a stack trace."""
    raised = {jh.IntakeError, jh.ParseError, jh.FetchError, jh.ExportBlocked,
              jh.PdfError, jh.YamlError}
    for error in raised:
        assert issubclass(error, jh.USER_ERRORS), error.__name__


@pytest.mark.parametrize("error, code", [
    (lambda: (_ for _ in ()).throw(jh.FetchError("behind a login wall")), jh.BLOCKED),
    (lambda: (_ for _ in ()).throw(jh.ParseError("not JSON")), jh.UNREADABLE),
    (lambda: (_ for _ in ()).throw(jh.PdfError("no browser")), jh.UNFIT),
    (lambda: (_ for _ in ()).throw(jh.IntakeError("no such file")), jh.BLOCKED),
])
def test_each_error_gets_the_exit_code_the_skills_document(error, code, capsys):
    assert jh.run_cli(lambda argv: error(), []) == code
    assert "Traceback" not in capsys.readouterr().err


# --- the review: a CV measured against nothing but itself ------------------

def test_the_weights_add_up_to_a_hundred():
    """The number is a sum of named parts, so the parts have to sum."""
    assert sum(jh.WEIGHTS.values()) == 100


def test_a_perfect_cv_scores_full_marks():
    profile = jh.Profile(
        personal=jh.Personal(name="Ada", surname="L", email="a@b.co",
                             phone="+49 170", city="Berlin", country="Germany",
                             headline="Data Engineer", github="https://github.com/ada"),
        summary="Data engineer who builds pipelines that stay up.",
        skills=["dbt", "Airflow"],
        experience=[jh.Role(position="Engineer", company="Acme", start="2021",
                            bullets=["Cut ETL runtime 35% by rewriting the dbt models.",
                                     "Ran the Airflow DAGs for 40 people."])])
    found = jh.review(profile)
    assert found.score == found.out_of == 100, jh.review_page(found)


def test_an_empty_profile_scores_nothing_and_does_not_raise():
    found = jh.review(jh.Profile())
    assert found.score == 0
    assert jh.review_page(found)


@pytest.mark.parametrize("line, quantified", [
    ("Cut ETL runtime by 35%.", True),
    ("Mentored two junior analysts.", True),
    # A worded quantity is still a measured outcome. A digits-only test reads
    # this as an adjective, which cost a real CV 20 points.
    ("Automated delivery with zero manual intervention.", True),
    ("Doubled the release cadence.", True),
    ("Worked at Acme from 2021 to 2024.", False),
    ("Configured Nginx as a reverse proxy for load balancing.", False),
])
def test_what_counts_as_a_figure(line, quantified):
    assert jh.is_quantified(line) is quantified


@pytest.mark.parametrize("line, weak", [
    ("Responsible for the ingestion pipelines", True),
    ("Involved in several cross-team projects", True),
    ("Helped with the migration", True),
    ("Built the ingestion pipelines", False),
    ("Owned the on-call rota", False),
])
def test_what_counts_as_a_duty_rather_than_a_result(line, weak):
    assert bool(jh.weak_opener(line)) is weak


def test_a_skill_shown_only_by_its_head_word_still_counts():
    """"Linux administration" is demonstrated by a bullet about hardening Linux
    servers. Calling that unshown is a finding a reader rightly ignores, and a
    checker that gets ignored stops being read at all."""
    profile = jh.Profile(
        skills=["Linux administration", "Jenkins"],
        experience=[jh.Role(company="Acme", bullets=["Hardened Linux servers."])])
    shown = next(d for d in jh.review(profile).dimensions if d.name == "shown")
    assert "Jenkins" in shown.findings[0].quote
    assert "Linux" not in shown.findings[0].quote


def test_the_order_dimension_ignores_roles_with_nothing_to_lead_with():
    """A role with no quantified line cannot be marked down for burying one."""
    profile = jh.Profile(experience=[
        jh.Role(company="A", bullets=["Cut runtime 35%.", "Did a thing."]),
        jh.Role(company="B", bullets=["Did a thing.", "Did another."])])
    order = next(d for d in jh.review(profile).dimensions if d.name == "order")
    assert order.points == order.out_of, order.tally


def test_the_score_is_the_sum_of_its_parts_and_nothing_else():
    """No hidden term. Every point traces to a dimension a reader can see."""
    profile = jh.Profile(
        personal=jh.Personal(name="Ada", surname="L", email="a@b.co"),
        experience=[jh.Role(company="Acme", bullets=["Responsible for things."])])
    found = jh.review(profile)
    assert found.score == sum(d.points for d in found.dimensions)
    assert found.out_of == sum(d.out_of for d in found.dimensions) == 100


def test_the_review_never_claims_to_predict_hiring():
    """The one thing this number must not be read as."""
    profile = jh.Profile(personal=jh.Personal(name="Ada", surname="L"),
                         experience=[jh.Role(company="A", bullets=["Cut 35%."])])
    page = jh.review_page(jh.review(profile)).lower()
    assert "not whether you will get a job" in page
    for wrong in ("chance of", "likely to be hired", "probability", "guarantee"):
        assert wrong not in page, wrong


# --- the advice half: a finding without it is a complaint ------------------

def test_every_dimension_says_what_to_do_about_itself():
    assert set(jh.ADVICE) == set(jh.WEIGHTS), "a dimension with no advice"
    for name, said in jh.ADVICE.items():
        assert len(said) > 40, f"{name}: too short to act on"


@pytest.mark.parametrize("line, expect", [
    ("Deployed a CI/CD pipeline with GitHub Actions", "release take"),
    ("Built a monitoring and alerting tool", "how fast does an alert"),
    ("Hardened Linux production servers", "how many machines"),
    ("Integrated HubSpot CRM via webhooks", "records or events"),
    ("Cut multi-cloud spend across AWS and GCP", "from what baseline"),
    ("Mentored the new starters", "how many people"),
    ("Reorganised the filing cabinet", "How many, how much, how fast"),
])
def test_the_question_fits_the_bullet(line, expect):
    """"Add a metric" is advice nobody can act on. The question has to be one
    the person can actually answer about that line."""
    assert expect.lower() in jh.ask_about(line).lower()


def test_every_unquantified_bullet_gets_a_question():
    profile = jh.Profile(experience=[jh.Role(company="A", bullets=[
        "Deployed a CI/CD pipeline.", "Wrote some documentation.",
        "Did an unusual thing nobody has a pattern for."])])
    evidence = next(d for d in jh.review(profile).dimensions
                    if d.name == "evidence")
    assert len(evidence.findings) == 3
    for f in evidence.findings:
        assert f.ask, f"no question for {f.quote!r}"
        assert f.quote, "a question with no line to attach it to"


def test_the_report_starts_with_the_biggest_win_not_the_lowest_bar():
    """A 0/10 is a smaller problem than a 4/30. Sending somebody at the small
    one first is how a review wastes their evening."""
    profile = jh.Profile(
        personal=jh.Personal(name="A", surname="B", email="a@b.co", phone="1",
                             city="X", country="Y", headline="Z",
                             github="https://g/a"),
        summary="s", skills=["dbt"],
        experience=[jh.Role(company="A", start="2021", bullets=[
            "Responsible for the pipelines.",
            "Involved in the migration."])])
    found = jh.review(profile)
    assert jh.biggest_win(found).name == "evidence", \
        [(d.name, d.points, d.out_of) for d in found.dimensions]
    page = jh.review_page(found)
    assert "START HERE" in page and "evidence -" in page


def test_the_advice_is_not_repeated_under_its_own_heading():
    """Saying it twice is how a report teaches people to skim it."""
    profile = jh.Profile(experience=[jh.Role(company="A", bullets=["Did work."])])
    page = jh.review_page(jh.review(profile))
    assert page.count("answer the questions below") == 1, page


def test_an_instruction_is_not_labelled_as_a_question():
    profile = jh.Profile(skills=["Jenkins"],
                         experience=[jh.Role(company="A", bullets=["Cut 35%."])])
    page = jh.review_page(jh.review(profile))
    for line in page.splitlines():
        if "ask yourself:" in line:
            assert line.rstrip().endswith("?"), line
        if line.strip().startswith("do:"):
            assert not line.rstrip().endswith("?"), line
