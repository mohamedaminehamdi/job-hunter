from pathlib import Path

import pytest
from jobhunt import (
    BLOCKING,
    Personal,
    Profile,
    Role,
    YamlError,
    build,
    load,
    save,
)


def blocking(profile: Profile) -> list[str]:
    return [i.path for i in profile.report() if i.severity == BLOCKING]


def messages(profile: Profile) -> str:
    return " ".join(i.message for i in profile.report())


def test_empty_profile_loads_and_reports_instead_of_raising():
    p = Profile()
    assert not p.is_renderable
    assert "personal.name" in blocking(p)


def test_complete_profile_is_renderable():
    p = Profile(
        personal=Personal(name="Ada", surname="Lovelace", email="ada@example.com"),
        experience=[Role(position="Engineer", company="Analytical", bullets=["Wrote note G."])],
    )
    assert p.is_renderable, p.report()






def test_bad_email_warns_but_does_not_block():
    p = Profile(
        personal=Personal(name="Ada", surname="L", email="not-an-email"),
        experience=[Role(position="E", company="C", bullets=["Real work."])],
    )
    assert p.is_renderable
    assert "does not look like an email" in messages(p)


def test_url_without_scheme_warns():
    p = Profile(
        personal=Personal(name="Ada", surname="L", email="a@b.co", github="github.com/ada"),
        experience=[Role(position="E", company="C", bullets=["Real work."])],
    )
    assert "http" in messages(p)


def test_role_without_bullets_warns():
    p = Profile(
        personal=Personal(name="Ada", surname="L", email="a@b.co"),
        experience=[Role(position="E", company="Acme")],
    )
    assert "Acme" in messages(p)


def test_missing_experience_and_education_blocks():
    p = Profile(personal=Personal(name="Ada", surname="L", email="a@b.co"))
    assert "experience" in blocking(p)


def test_issues_are_sorted_worst_first():
    p = Profile()
    rank = {"blocking": 0, "warning": 1, "info": 2}
    severities = [i.severity for i in p.report()]
    assert severities == sorted(severities, key=lambda s: rank[s])


def test_round_trip_through_yaml(tmp_path: Path):
    p = Profile(
        personal=Personal(name="Mohamed Amine", surname="Hamdi", email="a@b.co"),
        experience=[Role(position="DevSecOps Engineer", company="EcoG", bullets=["Owned CI/CD."])],
        skills=["Kubernetes", "Terraform"],
    )
    path = save(p, tmp_path / "profile.yaml")
    back = load(Profile, path)
    assert back == p
    assert back.personal.full_name == "Mohamed Amine Hamdi"


def test_load_missing_file_gives_empty_profile(tmp_path: Path):
    assert load(Profile, tmp_path / "nope.yaml") == Profile()


def test_load_malformed_yaml_names_the_line_instead_of_an_empty_profile(tmp_path: Path):
    """Swallowed here, a `{a: b}` on line 3 came out as "a name is required"
    and "add at least one role" - the failure the YAML reader was rewritten to
    stop, put back one layer up."""
    bad = tmp_path / "profile.yaml"
    bad.write_text("personal:\n  name: Ada\nskills: {a: b}\n", encoding="utf-8")
    with pytest.raises(YamlError) as caught:
        load(Profile, bad)
    assert caught.value.line == 3
    assert "this reader does not do" in str(caught.value)


def test_load_yaml_that_merely_lacks_fields_reports_rather_than_raising(tmp_path: Path):
    """The line between the two: a file this reader can parse but that says
    too little is a checklist, not an error."""
    thin = tmp_path / "profile.yaml"
    thin.write_text("skills:\n- Go\n", encoding="utf-8")
    p = load(Profile, thin)
    assert p.skills == ["Go"]
    assert "personal.name" in blocking(p)


def test_unknown_keys_are_dropped_not_fatal():
    p = build(Profile, {"skills": ["Go"], "favourite_colour": "blue"})
    assert p.skills == ["Go"]


def test_partial_section_salvaged_when_another_is_broken():
    """Hand-edited YAML and LLM extraction both produce half-valid documents."""
    p = build(Profile, {"skills": ["Go"], "experience": "not a list"})
    assert p.skills == ["Go"]
    assert p.experience == []


def test_period_formatting():
    assert Role(start="2024", end="2026").period == "2024 - 2026"
    assert Role(start="2024").period == "2024"
    assert Role().period == ""
