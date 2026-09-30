"""The LaTeX renderer, which is the default wherever a TeX engine exists.

The compile tests skip without an engine, but everything that can be checked
without one - escaping, template resolution, the fallback - is checked always,
because those are where the bugs were.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
import jobhunt as jh  # noqa: E402

needs_tex = pytest.mark.skipif(jh.find_tex() is None, reason="no TeX engine")


# --- escaping ---------------------------------------------------------------

@pytest.mark.parametrize("raw, want", [
    ("100%", r"100\%"),
    ("R&D", r"R\&D"),
    ("$5", r"\$5"),
    ("a_b", r"a\_b"),
    ("#1", r"\#1"),
    ("{x}", r"\{x\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
    ("C++", "C++"),
    ("Müller", "Müller"),
])
def test_every_latex_special_is_escaped(raw, want):
    assert jh.tex_escape(raw) == want


def test_a_backslash_does_not_escape_its_own_replacement():
    """Replacing in sequence turns a backslash into `\\textbackslash\\{\\}`,
    because the brace rules run after the backslash rule and mangle the braces
    it just inserted. One pass, or this breaks silently."""
    assert jh.tex_escape("\\") == r"\textbackslash{}"


@pytest.mark.parametrize("raw, want", [
    ("—", "---"), ("–", "--"), ("“x”", "``x''"), ("„y“", ",,y``"),
    ("ß", r"\ss{}"), ("•", r"\textbullet{}"), ("…", r"\ldots{}"),
    ("→", r"$\rightarrow$"), ("€", r"\texteuro{}"), ("·", r"$\cdot$"),
])
def test_characters_the_font_cannot_set_are_spelled_in_latex(raw, want):
    """These do not fail loudly - they come out as nothing at all. A German CV
    rendered before this fix printed 'Fussball' as 'FuSSball' and dropped every
    em dash on the page."""
    assert jh.tex_escape(raw) == want


def test_no_unicode_survives_that_would_be_dropped():
    """The whole escaped output has to be settable. Anything left outside the
    ranges the T1 encoding covers would vanish from the PDF without a word."""
    sample = "Fußball — Straße “x” • → 100% & C++ … €50 · ≥ ×"
    out = jh.tex_escape(sample)
    for char in out:
        assert char in jh._TEX_UNICODE or ord(char) < 0x180, repr(char)


def test_a_separator_is_never_fed_through_the_escaper():
    """`tex_escape(" $\\cdot$ ".join(parts))` escapes the dollars in the
    separator, and the CV prints a literal `$\\cdot$` between every field.
    That shipped in the first version of this renderer."""
    assert jh._tex_dots("a", "b") == r"a $\cdot$ b"
    assert r"\$" not in jh._tex_dots("a", "b")


# --- the contact line and the letter ----------------------------------------

def test_links_are_printed_without_their_scheme_and_still_link():
    """The full https:// URL ran off the right margin on a real CV."""
    who = jh.Personal(name="Ada", email="a@b.co", github="https://github.com/ada",
                      linkedin="https://linkedin.com/in/ada-lovelace")
    line = jh._tex_contact(who)
    assert "https://" not in line.replace(r"\href{https://", "")
    assert r"\href{https://github.com/ada}{github.com/ada}" in line
    assert "a@b.co" in line


def test_a_url_hyperref_would_choke_on_is_printed_not_linked():
    assert jh._tex_link("https://x.y/a%20b") == "x.y/a\\%20b"


def test_the_latex_letter_writes_the_date_out_and_names_the_role(profile, job):
    """The HTML letter said "7 September 2026" and "Application: ..."; the
    LaTeX one printed 2026-09-07 and nothing."""
    letter = jh.write_letter(profile, job, {"greeting": "Dear Zeta,", "paragraphs": ["x"],
                                            "closing": "Kind regards,"})
    letter.written_on = "2026-09-07"
    source = jh.letter_latex(letter)
    assert "7 September 2026" in source and "2026-09-07" not in source
    assert r"\cvsubject{Application: Senior Data Engineer}" in source


def test_an_old_two_argument_template_still_gets_a_document(profile):
    """A hand-written template from before `\\cventrydated` existed. The
    prelude's `\\providecommand` gives it the old look, not a compile error."""
    old = ("%%JOBHUNT-BODY%%\n")
    source = jh.cv_latex(profile, template=old)
    assert r"\providecommand{\cventrydated}" in source
    assert r"\cventrydated{Data Engineer}" in source


# --- templates --------------------------------------------------------------

def test_a_built_in_template_resolves_by_name():
    assert jh.resolve_template("plain") is jh.PLAIN_TEX
    assert jh.resolve_template("PLAIN") is jh.PLAIN_TEX


def test_a_path_to_a_tex_file_resolves_to_its_contents(tmp_path):
    mine = tmp_path / "mine.tex"
    mine.write_text("%%JOBHUNT-BODY%%", encoding="utf-8")
    assert jh.resolve_template(str(mine)) == "%%JOBHUNT-BODY%%"


def test_an_unknown_template_resolves_to_nothing_rather_than_guessing():
    assert jh.resolve_template("fancy") is None
    assert jh.resolve_template("") is None
    assert jh.resolve_template(None) is None


def test_the_body_marker_is_a_latex_comment():
    """An unreplaced `%%JOBHUNT-BODY%%` is a comment, so a template that was
    half-filled still compiles into something a person can look at and
    diagnose. A marker spelled `{{body}}` would be a syntax error instead.

    Only the body marker gets this: the accent one sits inside a braced
    argument, where a stray `%` would comment out the closing brace. It is
    always substituted, so that is a trade rather than a hole - but it is the
    reason this test names one marker instead of looping over all of them.
    """
    for name, template in jh.LATEX_TEMPLATES.items():
        body = [line for line in template.splitlines()
                if "%%JOBHUNT-BODY%%" in line]
        assert body, f"{name} has nowhere to put a document"
        for line in body:
            assert line.strip().startswith("%"), line


def test_no_template_carries_a_doubled_backslash():
    r"""`\documentclass` is not a command - it is a line break followed by the
    word "documentclass", and TeX says "There's no line here to end" on line 2
    and stops. One patch got this wrong and the letter template shipped broken
    for as long as it took the compile test to run."""
    for name, template in jh.LATEX_TEMPLATES.items():
        assert "\\\\" not in template.replace("\\\\\n", ""), name


def test_the_body_reaches_the_page():
    cv = jh.Profile(personal=jh.Personal(name="Ada", surname="L"),
                    experience=[jh.Role(company="ACME", position="Dev",
                                        bullets=["Cut runtime 35%"])])
    out = jh.cv_latex(cv)
    assert "Ada L" in out
    assert r"Cut runtime 35\%" in out
    assert "%%JOBHUNT-BODY%%" not in out
    assert "%%JOBHUNT-ACCENT%%" not in out


# --- choosing a renderer ----------------------------------------------------

def test_latex_is_the_default_when_an_engine_is_there(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(jh, "find_tex", lambda: "/usr/bin/pretend")
    monkeypatch.setattr(jh, "write_pdf_latex",
                        lambda src, path, engine=None: seen.update(src=src))
    cv = jh.Profile(personal=jh.Personal(name="Ada", surname="L"))
    assert jh.render_pdf(cv, tmp_path / "cv.pdf") == "latex"
    assert "documentclass" in seen["src"]


def test_the_browser_still_renders_when_there_is_no_tex(tmp_path, monkeypatch):
    """The point of the default is that it is a default. A machine with Python
    and a browser is still enough - that is the whole promise of the project,
    and a TeX dependency would end it."""
    seen = {}
    monkeypatch.setattr(jh, "find_tex", lambda: None)
    monkeypatch.setattr(jh, "write_pdf", lambda page, path: seen.update(page=page))
    cv = jh.Profile(personal=jh.Personal(name="Ada", surname="L"))
    assert jh.render_pdf(cv, tmp_path / "cv.pdf") == "browser"
    assert "<" in seen["page"], "that is not HTML"


def test_an_explicit_template_is_used_even_where_tex_was_not_found(monkeypatch,
                                                                   tmp_path):
    """Asking for one by name is an instruction, not a preference. Falling back
    silently would hand back a browser PDF that looks nothing like the ask."""
    monkeypatch.setattr(jh, "find_tex", lambda: None)
    monkeypatch.setattr(jh, "write_pdf_latex",
                        lambda src, path, engine=None: None)
    cv = jh.Profile(personal=jh.Personal(name="Ada", surname="L"))
    assert jh.render_pdf(cv, tmp_path / "cv.pdf", template="plain") == "latex"


def test_a_template_that_does_not_exist_says_so_by_name(tmp_path):
    cv = jh.Profile(personal=jh.Personal(name="Ada", surname="L"))
    with pytest.raises(jh.PdfError, match="No template called 'fancy'"):
        jh.render_pdf(cv, tmp_path / "cv.pdf", template="fancy")


def test_a_letter_gets_the_letter_template_not_the_cv_one(tmp_path, monkeypatch):
    """A CV set in LaTeX beside a letter set by the browser is a mismatched
    pair, and the pair is what gets attached to one email."""
    seen = {}
    monkeypatch.setattr(jh, "find_tex", lambda: "/usr/bin/pretend")
    monkeypatch.setattr(jh, "write_pdf_latex",
                        lambda src, path, engine=None: seen.update(src=src))
    letter = jh.CoverLetter(personal=jh.Personal(name="Ada", surname="L"),
                            paragraphs=["Dear team,"])
    assert jh.render_pdf(letter, tmp_path / "letter.pdf") == "latex"
    assert "parskip" in seen["src"], "that is the CV template"


def test_no_engine_and_no_browser_still_names_the_fix(tmp_path, monkeypatch):
    monkeypatch.setattr(jh, "find_tex", lambda: None)
    with pytest.raises(jh.PdfError, match="tectonic"):
        jh.write_pdf_latex("x", tmp_path / "cv.pdf")


def test_the_engine_can_be_pointed_at(monkeypatch):
    monkeypatch.setenv("JOBHUNT_TEX", "definitely-not-a-real-engine")
    assert jh.find_tex() is None
    monkeypatch.setenv("JOBHUNT_TEX", "python3")
    assert jh.find_tex().endswith("python3")


# --- it actually compiles ---------------------------------------------------

@needs_tex
def test_a_cv_full_of_latex_hostile_characters_compiles(tmp_path):
    """Every character that ends a LaTeX compile, in one document."""
    cv = jh.Profile(
        personal=jh.Personal(name="Brahim & Khalil", surname="Bouguerra",
                             headline="100% C++ — R&D", email="a_b@c.de",
                             github="github.com/kb_dev"),
        summary="Straße, Fußball, 50%_Anteil, $5, {x}, ~, ^, #1.",
        experience=[jh.Role(company="ACME & Co", position="Dev", start="2024",
                            bullets=["Cut runtime 35% — from 8h to 5h",
                                     "Used a_b {x} ~ ^ and $5"])],
        education=[jh.Education(level="B.Eng.", field_of_study="Informatik",
                                institution="BHT Berlin", start="2024")],
        skills=["C / C++", "R&D", "100% coverage"],
        languages=[jh.Language(name="Français", level="C1")])
    out = tmp_path / "cv.pdf"
    jh.write_pdf_latex(jh.cv_latex(cv), out)
    assert out.read_bytes().startswith(b"%PDF")


@needs_tex
def test_a_letter_compiles(tmp_path):
    letter = jh.CoverLetter(
        personal=jh.Personal(name="Ada", surname="L", email="a@b.co"),
        greeting="Sehr geehrte Damen und Herren,",
        paragraphs=["Ich bewerbe mich um die Stelle — 100% Interesse.",
                    "Mit R&D-Erfahrung in C++."],
        closing="Mit freundlichen Grüßen", signature="Ada L")
    out = tmp_path / "letter.pdf"
    jh.write_pdf_latex(jh.letter_latex(letter), out)
    assert out.read_bytes().startswith(b"%PDF")


@needs_tex
def test_a_broken_template_reports_the_engine_s_own_complaint(tmp_path):
    """A LaTeX error is usually one line and usually exact. Swallowing it and
    saying "the PDF could not be made" throws away the only useful part."""
    with pytest.raises(jh.PdfError) as raised:
        jh.write_pdf_latex(r"\documentclass{article}\begin{document}"
                           r"\thisCommandDoesNotExist\end{document}",
                           tmp_path / "x.pdf")
    assert "thisCommandDoesNotExist" in str(raised.value) or \
           "Undefined control sequence" in str(raised.value)
