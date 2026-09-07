"""Rendering: HTML assertions, and the rule that blocks an export.

No PDF is produced here - that needs a browser and belongs in a manual check,
not in a suite that has to run anywhere.
"""

import pytest

from job_hunter import render
from job_hunter.generate import cover_letter, cv
from job_hunter.profile.models import Profile

CV_REPLY = {
    "summary": "Data engineer with production pipeline experience.",
    "roles": [{"index": 0, "bullets": ["Cut ETL runtime by 35% by rewriting the dbt models."]}],
    "projects": [0],
    "skills": ["Python", "dbt"],
}
LETTER_REPLY = {
    "greeting": "Dear Hiring Team,",
    "paragraphs": ["I build data pipelines."],
    "closing": "Kind regards,",
}


@pytest.fixture
def document(profile, job):
    return cv.assemble(profile, job, CV_REPLY)


@pytest.fixture
def letter(profile, job):
    return cover_letter.assemble(profile, job, LETTER_REPLY)


def test_cv_html_carries_the_content(document):
    html = render.to_html(document)
    assert "Ada Lovelace" in html
    assert "Cut ETL runtime by 35%" in html
    assert "TU Berlin" in html
    assert "dbt Analytics Engineer" in html
    assert html.strip().startswith("<!doctype html>")


def test_letter_html_carries_the_content(letter):
    html = render.to_html(letter)
    assert "Dear Hiring Team," in html
    assert "I build data pipelines." in html
    assert "Ada Lovelace" in html


def test_plain_profile_renders_too(profile):
    """The CV template takes a Profile, so a profile can be printed as-is."""
    assert "Ada Lovelace" in render.cv_html(profile)


def test_font_stack_survives_autoescaping(document):
    """An escaped quote in a family name silently drops the whole page to serif."""
    import re

    declarations = re.findall(r"font-family:[^;]*;", render.to_html(document))
    assert declarations
    for declaration in declarations:
        assert '"Segoe UI"' in declaration
        assert "&#" not in declaration


def test_user_content_is_escaped(job):
    """Everything except the theme is data: a profile is not allowed to inject HTML."""
    nasty = Profile.model_validate({
        "personal": {"name": "<script>alert(1)</script>"},
        "summary": "5 > 3 & sensible",
    })
    html = render.cv_html(nasty)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "5 &gt; 3 &amp; sensible" in html


def test_branded_theme_uses_the_colour(letter, job):
    html = render.to_html(letter, theme=render.branded(job.brand_color))
    assert "#7b2ff7" in html
    assert render.branded(job.brand_color).is_branded


def test_a_bad_colour_is_refused_not_escaped():
    """The accent reaches a stylesheet, so it is validated, not sanitised."""
    for bad in ("red; } body { display:none", "url(x)", "", "#12", "javascript:x"):
        assert render.branded(bad) is render.NEUTRAL
    assert render.branded("#ABCDEF").accent == "#abcdef"


def test_unknown_theme_name_falls_back():
    assert render.resolve("nonsense") is render.NEUTRAL
    assert render.resolve(None) is render.NEUTRAL
    assert render.resolve("classic").name == "classic"


def test_screen_and_print_both_have_page_margins(document):
    html = render.to_html(document)
    assert "@page" in html                # printing
    assert "@media screen" in html        # or the review frame clips right-aligned dates
    # Order matters: the base `body { margin: 0 }` rule would otherwise override the
    # screen block's centring, since the two have equal specificity.
    assert html.index("@media screen") > html.index("body {")


def test_export_refuses_a_blocked_document(profile, job, tmp_path):
    blocked = cv.assemble(profile, job, {**CV_REPLY, "summary": "Engineer at [Company]."})
    with pytest.raises(render.ExportBlocked) as caught:
        render.export(blocked, tmp_path / "cv.pdf")

    assert "not ready to export" in str(caught.value)
    assert caught.value.issues
    assert not (tmp_path / "cv.pdf").exists()  # nothing was written


def test_export_of_a_clean_document_reaches_the_pdf_step(document, tmp_path, monkeypatch):
    """The blocking check passes and the renderer is handed real HTML."""
    seen = {}

    def fake_write(html, path):
        seen["html"] = html
        path.write_bytes(b"%PDF-1.4 fake")
        return path

    monkeypatch.setattr(render, "write_pdf", fake_write)
    result = render.export(document, tmp_path / "cv.pdf")
    assert result.exists()
    assert "Ada Lovelace" in seen["html"]
