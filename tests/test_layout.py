"""The page as a person sees it: what is on it, in what order, on how many pages.

Every renderer is asked the same questions here, because the bug this file
exists for was a section that reached the HTML and the markdown and never the
LaTeX - and no test looked at the three side by side.
"""

import zlib

import jobhunt as jh
import pytest
from jobhunt import Personal, Profile, Role

needs_browser = pytest.mark.skipif(jh.find_browser() is None, reason="no browser")
needs_tex = pytest.mark.skipif(jh.find_tex() is None, reason="no TeX engine")

HEADINGS = ("Experience", "Projects", "Education", "Skills", "Certifications", "Languages")


def rendered(document):
    return {"html": jh.cv_html(document), "markdown": jh.cv_markdown(document),
            "latex": jh.cv_latex(document)}


# --- parity ------------------------------------------------------------------

@pytest.mark.parametrize("heading", HEADINGS)
def test_every_section_reaches_every_renderer(profile, heading):
    """The fixture has all six. The LaTeX renderer shipped without a
    Certifications section, and a real CV lost its AWS certificate."""
    for name, page in rendered(profile).items():
        assert heading in page, f"{heading} missing from {name}"


def test_the_summary_reaches_every_renderer(profile):
    for name, page in rendered(profile).items():
        assert "pipelines that stay up" in page, name


def test_dates_print_as_a_person_writes_them(profile):
    profile.experience[0].start, profile.experience[0].end = "2021-03", "Present"
    for name, page in rendered(profile).items():
        assert "Mar 2021" in page, name
        assert "2021-03" not in page, name
    assert "Mar 2021 -- Present" in jh.cv_latex(profile)   # the en dash, as TeX sets it


# --- order --------------------------------------------------------------------

def order_in(html):
    """The headings in the order the page shows them."""
    present = [h for h in HEADINGS if f"<h2>{h}</h2>" in html]
    return sorted(present, key=lambda h: html.index(f"<h2>{h}</h2>"))


def test_an_experienced_hire_leads_with_experience(profile):
    """The fixture: a degree finished in 2019, five years of roles."""
    assert not jh.is_student(profile)
    assert order_in(jh.cv_html(profile))[:2] == ["Experience", "Projects"]


def test_a_student_leads_with_the_degree(profile):
    profile.education[0].end = "2099"
    assert jh.is_student(profile)
    assert order_in(jh.cv_html(profile))[0] == "Education"
    markdown, latex = jh.cv_markdown(profile), jh.cv_latex(profile)
    assert markdown.index("## Education") < markdown.index("## Experience")
    assert latex.index("{Education}") < latex.index("{Experience}")


def test_under_two_years_of_work_counts_as_a_student():
    fresh = Profile(personal=Personal(name="Ada"),
                    experience=[Role(position="Intern", company="X", start="2025-06",
                                     end="Present")])
    assert jh.is_student(fresh)


def test_the_order_can_be_given(profile):
    html = jh.cv_html(profile, order=["skills", "education"])
    assert order_in(html)[:2] == ["Skills", "Education"]
    assert order_in(html)[2:] == ["Experience", "Projects", "Certifications", "Languages"]


def test_a_tailored_cv_remembers_its_order(profile, job):
    document = jh.tailor(profile, job, {"summary": "", "roles": [{"index": 0}],
                                        "projects": [], "skills": []})
    document.section_order = ["skills"]
    assert order_in(jh.cv_html(document))[0] == "Skills"


# --- density ------------------------------------------------------------------

def test_a_tighter_density_sets_a_smaller_page(profile):
    normal, dense = jh.cv_html(profile), jh.cv_html(profile, density="dense")
    assert "font-size: 10.5pt" in normal and "margin: 16mm 15mm" in normal
    assert "font-size: 9.5pt" in dense and "margin: 11mm 12mm" in dense
    tex = jh.cv_latex(profile, density="compact")
    assert "documentclass[10pt" in tex and "margin=15mm" in tex
    assert "%%JOBHUNT" not in tex, "a marker was left unfilled"


def test_a_heading_never_ends_a_page(profile):
    assert "break-after: avoid" in jh.cv_html(profile)
    assert "\\filbreak" in jh.cv_latex(profile)


# --- trimming ------------------------------------------------------------------

def long_profile():
    return Profile(
        personal=Personal(name="Ada", surname="L", email="a@b.co"),
        experience=[Role(position=f"Engineer {i}", company=f"Co{i}", start=str(2015 + i),
                         end=str(2016 + i), bullets=[f"Did thing {j} at Co{i}." for j in range(8)])
                    for i in range(3)],
        projects=[jh.Project(name=f"p{i}", description="First sentence. Second sentence here.")
                  for i in range(4)],
        education=[jh.Education(level="BSc", institution="U", courses=["A", "B"])])


def test_trimming_is_deterministic_and_says_what_went():
    document = long_profile()
    once, cuts = jh.trimmed(document, 1)
    assert [len(r.bullets) for r in once.experience] == [5, 5, 5]
    assert once.education[0].courses == [] and once.projects[0].description == "First sentence."
    assert len(once.projects) == 4
    assert any("3 bullet(s) from Co0" in c for c in cuts) and any("course list" in c for c in cuts)
    twice, more = jh.trimmed(document, 2)
    assert [len(r.bullets) for r in twice.experience] == [5, 3, 3] and len(twice.projects) == 3
    assert [len(r.bullets) for r in document.experience] == [8, 8, 8], "the original is untouched"
    same, none = jh.trimmed(document, 0)
    assert same is document and none == []


def test_the_page_budget_is_one_unless_the_career_is_long(profile):
    assert jh.page_budget(profile) == 1
    veteran = Profile(experience=[Role(position="A", company="X", start="2005", end="Present")])
    assert jh.page_budget(veteran) == 2


# --- counting pages ------------------------------------------------------------

def test_pages_are_read_from_the_page_tree(tmp_path):
    plain = tmp_path / "plain.pdf"
    plain.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Pages /Kids [2 0 R] /Count 3 >> endobj\n")
    assert jh.pdf_pages(plain) == 3
    packed = tmp_path / "packed.pdf"
    inner = zlib.compress(b"<< /Type /Pages /Kids [] /Count 2 >>")
    packed.write_bytes(b"%PDF-1.5\n1 0 obj << /Type /ObjStm /Filter /FlateDecode >>\nstream\n"
                       + inner + b"\nendstream\nendobj\n")
    assert jh.pdf_pages(packed) == 2
    assert jh.pdf_pages(tmp_path / "nowhere.pdf") == 0


def test_over_budget_is_reported_and_the_ladder_stops_at_typography(profile, tmp_path, monkeypatch):
    """Without --fit the content is never touched: the ladder runs to the
    densest setting, writes the PDF anyway, and says it is over."""
    seen = []

    def fake_pdf(html, path):
        seen.append(html)
        path.write_bytes(b"%PDF-1.4\n<< /Type /Pages /Count 2 >>")
    monkeypatch.setattr(jh, "find_tex", lambda: None)
    monkeypatch.setattr(jh, "write_pdf", fake_pdf)
    made = jh.export(profile, tmp_path / "cv.pdf")
    assert made == "browser" and made.pages == 2 and made.over and made.budget == 1
    assert made.density == "dense" and made.trimmed == ()
    assert len(seen) == 3, "normal, compact, dense - and no fourth without --fit"


def test_with_fit_the_content_is_cut_and_every_cut_named(tmp_path, monkeypatch):
    document = long_profile()
    pages = iter([2, 2, 2, 2, 1])

    def fake_pdf(html, path):
        path.write_bytes(b"%PDF-1.4\n<< /Type /Pages /Count " + str(next(pages)).encode() + b" >>")
    monkeypatch.setattr(jh, "find_tex", lambda: None)
    monkeypatch.setattr(jh, "write_pdf", fake_pdf)
    made = jh.export(document, tmp_path / "cv.pdf", fit=True)
    assert made.pages == 1 and not made.over
    assert any("project(s)" in cut for cut in made.trimmed)


def test_a_letter_is_never_fitted(profile, job, tmp_path, monkeypatch):
    letter = jh.write_letter(profile, job, {"greeting": "Hi,", "paragraphs": ["x"],
                                            "closing": "Bye,"})
    calls = []
    monkeypatch.setattr(jh, "find_tex", lambda: None)
    monkeypatch.setattr(jh, "write_pdf", lambda html, path: calls.append(1))
    jh.export(letter, tmp_path / "letter.pdf")
    assert len(calls) == 1


# --- the real thing ------------------------------------------------------------

@needs_browser
def test_a_long_cv_comes_out_on_one_page_in_the_browser(tmp_path):
    made = jh.export(long_profile(), tmp_path / "cv.pdf", fit=True, prefer="browser")
    assert made == "browser" and made.pages == 1, (made.pages, made.density, made.trimmed)
    assert made.density != "normal" or made.trimmed, "it should have had to tighten"


@needs_tex
def test_a_long_cv_comes_out_on_one_page_in_latex(tmp_path):
    made = jh.export(long_profile(), tmp_path / "cv.pdf", fit=True)
    assert made == "latex" and made.pages == 1, (made.pages, made.density, made.trimmed)


@needs_tex
def test_the_latex_cv_reports_its_pages_and_keeps_every_section(profile, tmp_path):
    made = jh.export(profile, tmp_path / "cv.pdf")
    assert made == "latex" and made.pages == 1
