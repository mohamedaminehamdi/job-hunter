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
def test_the_browser_does_not_hold_the_run_open(tmp_path):
    """Chrome lingers after writing; waiting on it turns 2s into 5 minutes."""
    import time
    start = time.monotonic()
    jh.write_pdf("<p>hi</p>", tmp_path / "x.pdf")
    assert time.monotonic() - start < 30


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
