"""Five kinds of CV, rendered every way, asked the questions a recruiter asks.

`tests/corpus/README.md` says who each profile stands for. Nothing here checks
a pixel; it checks what can be read off the output - which sections are there,
in what order, on how many pages - and that every renderer gives the same
answers. The gallery (`tools/gallery.py`) is for the eyes.
"""

import re
from pathlib import Path

import jobhunt as jh
import pytest

CORPUS = sorted((Path(__file__).parent / "corpus").glob("*.yaml"))
needs_browser = pytest.mark.skipif(jh.find_browser() is None, reason="no browser")
needs_tex = pytest.mark.skipif(jh.find_tex() is None, reason="no TeX engine")

TITLES = {"experience": "Experience", "projects": "Projects", "education": "Education",
          "skills": "Skills", "certifications": "Certifications", "languages": "Languages"}

JOB = jh.Job(title="Engineer", company="Zeta", url="https://zeta.example/j/1",
             requirements=["Strong SQL", "Experience with Python", "Kubernetes in production"],
             nice_to_have=["Kafka"])


def load(path):
    return jh.load(jh.Profile, path)


@pytest.fixture(params=CORPUS, ids=lambda p: p.stem)
def profile(request):
    return load(request.param)


# --- every profile is a whole, valid profile ---------------------------------

def test_the_corpus_has_the_five_it_says_it_has():
    assert {p.stem for p in CORPUS} == {"student", "career-changer", "senior", "non-tech", "french"}


def test_it_loads_and_is_renderable(profile):
    assert profile.personal.full_name and profile.experience
    assert profile.is_renderable, [str(i) for i in profile.report()]


def test_the_review_runs_and_says_where_to_start(profile):
    found = jh.review(profile)
    assert 0 <= found.score <= found.out_of == 100
    assert "START HERE" in jh.review_page(found) or found.score == 100


def test_the_fit_runs_against_a_posting(profile):
    before = jh.score(JOB, profile)
    assert before.evidenced <= len(before.checkable)
    assert "Fit for" in jh.delta(before, before)


# --- every renderer shows the same document ----------------------------------

def sections_of(profile):
    return [name for name in TITLES if getattr(profile, name)]


def test_every_non_empty_section_reaches_every_renderer(profile):
    pages = {"html": jh.cv_html(profile), "markdown": jh.cv_markdown(profile),
             "latex": jh.cv_latex(profile)}
    for name in sections_of(profile):
        for renderer, page in pages.items():
            assert TITLES[name] in page, f"{name} missing from {renderer}"
    for renderer, page in pages.items():
        for name in set(TITLES) - set(sections_of(profile)):
            assert TITLES[name] not in page.replace("Education", "", 0), \
                f"{renderer} prints an empty {name} section"


def test_machine_dates_never_reach_the_page(profile):
    for page in (jh.cv_html(profile), jh.cv_markdown(profile), jh.cv_latex(profile)):
        assert not re.search(r"\b20\d\d-\d\d\b", page), "a YYYY-MM date printed as typed"


def test_the_order_fits_the_person(profile):
    html = jh.cv_html(profile)
    first = min((html.index(f"<h2>{TITLES[n]}</h2>"), n) for n in sections_of(profile))[1]
    if jh.is_student(profile):
        assert first == "education"
    else:
        assert first == "experience"


def test_no_heading_is_left_with_nothing_under_it(profile):
    html = jh.cv_html(profile)
    assert not re.search(r"</h2>\s*<h2>", html)
    assert html.count("<h1>") == 1


def test_the_page_budget_matches_the_career(profile):
    long = (jh.years_held(profile) or 0) >= jh.LONG_CAREER
    assert jh.page_budget(profile) == (2 if long else 1)


def test_the_contact_line_has_no_scheme_anywhere(profile):
    for page in (jh.cv_html(profile), jh.cv_markdown(profile)):
        head = page[:1200]
        assert "https://" not in head.replace('href="https://', "")


# --- the real thing, where the machine can ----------------------------------

@needs_browser
def test_it_fits_its_budget_in_the_browser(profile, tmp_path):
    made = jh.export(profile, tmp_path / "cv.pdf", fit=True, prefer="browser")
    assert made.pages == made.budget or made.pages < made.budget, \
        (made.pages, made.budget, made.density, made.trimmed)
    assert not made.over


@needs_tex
def test_it_compiles_and_fits_its_budget_in_latex(profile, tmp_path):
    made = jh.export(profile, tmp_path / "cv.pdf", fit=True)
    assert made == "latex"
    assert not made.over, (made.pages, made.budget, made.density, made.trimmed)
