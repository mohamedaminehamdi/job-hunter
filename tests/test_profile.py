from pathlib import Path

from job_hunter.profile import store
from job_hunter.profile.models import Education, Personal, Profile, Role, Severity


def blocking(profile: Profile) -> list[str]:
    return [i.path for i in profile.report() if i.severity == Severity.BLOCKING]


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


def test_placeholder_text_blocks_rendering():
    """The failure mode that reached a real PDF in the predecessor tool."""
    p = Profile(
        personal=Personal(name="[Your Name]", surname="Hamdi", email="a@b.co"),
        experience=[Role(position="Engineer", company="Acme", bullets=["Did work."])],
    )
    assert not p.is_renderable
    assert any("placeholder" in i.message.lower() for i in p.report())


def test_placeholder_found_in_nested_list():
    p = Profile(
        personal=Personal(name="Ada", surname="L", email="a@b.co"),
        education=[Education(institution="INSAT", courses=["[Grade]"])],
        experience=[Role(position="E", company="C", bullets=["Real work."])],
    )
    assert not p.is_renderable
    assert any(i.path.startswith("education[0].courses") for i in p.report())


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
    assert severities == sorted(severities, key=lambda s: rank[s.value])


def test_round_trip_through_yaml(tmp_path: Path):
    p = Profile(
        personal=Personal(name="Mohamed Amine", surname="Hamdi", email="a@b.co"),
        experience=[Role(position="DevSecOps Engineer", company="EcoG", bullets=["Owned CI/CD."])],
        skills=["Kubernetes", "Terraform"],
    )
    path = store.save(p, tmp_path / "profile.yaml")
    back = store.load(path)
    assert back == p
    assert back.personal.full_name == "Mohamed Amine Hamdi"


def test_load_missing_file_gives_empty_profile(tmp_path: Path):
    assert store.load(tmp_path / "nope.yaml") == Profile()


def test_load_malformed_yaml_gives_empty_profile(tmp_path: Path):
    bad = tmp_path / "profile.yaml"
    bad.write_text("this: [unclosed", encoding="utf-8")
    assert store.load(bad) == Profile()


def test_unknown_keys_are_dropped_not_fatal():
    p = store.from_dict({"skills": ["Go"], "favourite_colour": "blue"})
    assert p.skills == ["Go"]


def test_partial_section_salvaged_when_another_is_broken():
    """Hand-edited YAML and LLM extraction both produce half-valid documents."""
    p = store.from_dict({"skills": ["Go"], "experience": "not a list"})
    assert p.skills == ["Go"]
    assert p.experience == []


def test_period_formatting():
    assert Role(start="2024", end="2026").period == "2024 - 2026"
    assert Role(start="2024").period == "2024"
    assert Role().period == ""
