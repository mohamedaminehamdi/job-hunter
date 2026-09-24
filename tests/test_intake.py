"""Getting somebody's CV into a profile.

The split that matters: a YAML profile is read deterministically and needs no
model, and a CV in any other format is words the agent has to map onto the
schema itself. Nothing here calls a model, and nothing here guesses.
"""

import jobhunt as jh
import pytest


def test_a_yaml_profile_needs_no_model(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text("personal:\n  name: Ada\n  surname: Lovelace\n"
                    "skills: [Go, Kubernetes]\n", encoding="utf-8")
    profile = jh.load(jh.Profile, path)
    assert profile.personal.full_name == "Ada Lovelace"
    assert profile.skills == ["Go", "Kubernetes"]


def test_yaml_that_is_not_a_mapping_gives_an_empty_profile(tmp_path):
    """Reading never raises: the report is where the user finds out."""
    path = tmp_path / "profile.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    profile = jh.load(jh.Profile, path)
    assert profile == jh.Profile()
    assert not profile.is_renderable


def test_plain_text_is_read_verbatim(tmp_path):
    path = tmp_path / "cv.txt"
    path.write_text("Ada Lovelace\nWrote note G.\n", encoding="utf-8")
    assert jh.read_cv_text(path) == "Ada Lovelace\nWrote note G.\n"


def test_an_unreadable_format_says_what_is_readable(tmp_path):
    path = tmp_path / "cv.pages"
    path.write_text("x")
    with pytest.raises(jh.IntakeError, match="Readable here"):
        jh.read_cv_text(path)


def test_a_missing_file_says_so(tmp_path):
    with pytest.raises(jh.IntakeError, match="No such file"):
        jh.read_cv_text(tmp_path / "nope.pdf")


# --- links a printed CV loses ----------------------------------------------

def test_a_scheme_stripped_by_printing_is_put_back():
    """A CV this tool rendered, printed, and read back in arrives bare, and the
    check would then complain about three links that were right all along."""
    profile = jh.Profile(personal=jh.Personal(
        github="github.com/ada", linkedin="www.linkedin.com/in/ada",
        website="ada.dev/about"))
    fixed = jh.restore_scheme(profile).personal
    assert fixed.github == "https://github.com/ada"
    assert fixed.linkedin == "https://www.linkedin.com/in/ada"
    assert fixed.website == "https://ada.dev/about"


def test_a_link_that_already_has_one_is_left_alone():
    profile = jh.Profile(personal=jh.Personal(github="http://github.com/ada"))
    assert jh.restore_scheme(profile).personal.github == "http://github.com/ada"


def test_something_that_is_not_a_url_is_not_made_into_one():
    profile = jh.Profile(personal=jh.Personal(website="ask me"))
    assert jh.restore_scheme(profile).personal.website == "ask me"
