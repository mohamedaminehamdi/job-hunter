import json

import pytest

from job_hunter.profile import intake
from job_hunter.profile.intake import IntakeError


def test_yaml_intake_needs_no_model(tmp_path):
    path = tmp_path / "me.yaml"
    path.write_text(
        "personal:\n  name: Ada\n  surname: Lovelace\nskills: [Go, Kubernetes]\n",
        encoding="utf-8",
    )
    result = intake.from_file(path)
    assert result.profile.personal.full_name == "Ada Lovelace"
    assert result.profile.skills == ["Go", "Kubernetes"]
    assert result.extracted is False  # no model touched it


def test_unsupported_extension_rejected(tmp_path):
    path = tmp_path / "cv.pages"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(IntakeError, match="Unsupported file type"):
        intake.from_file(path)


def test_missing_file_rejected(tmp_path):
    with pytest.raises(IntakeError, match="No such file"):
        intake.from_file(tmp_path / "ghost.pdf")


def test_yaml_that_is_not_a_mapping_rejected(tmp_path):
    path = tmp_path / "me.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(IntakeError, match="mapping"):
        intake.from_file(path)


def test_plain_text_read_verbatim(tmp_path):
    path = tmp_path / "cv.txt"
    path.write_text("Ada Lovelace\nEngineer", encoding="utf-8")
    assert "Ada Lovelace" in intake.read_text(path)


def test_empty_text_extraction_rejected():
    with pytest.raises(IntakeError, match="empty"):
        intake.from_text("   ")


# --- parse_json: models do not respect "return only JSON" ---

def test_parse_plain_json():
    assert intake.parse_json('{"skills": ["Go"]}') == {"skills": ["Go"]}


def test_parse_json_in_code_fence():
    raw = '```json\n{"skills": ["Go"]}\n```'
    assert intake.parse_json(raw) == {"skills": ["Go"]}


def test_parse_json_wrapped_in_prose():
    raw = 'Here is the profile:\n{"skills": ["Go"]}\nHope that helps!'
    assert intake.parse_json(raw) == {"skills": ["Go"]}


def test_parse_json_rejects_non_object():
    with pytest.raises(IntakeError, match="JSON object"):
        intake.parse_json("[1, 2, 3]")


def test_parse_json_reports_when_no_json_present():
    with pytest.raises(IntakeError, match="did not return JSON"):
        intake.parse_json("I'm sorry, I can't help with that.")


def test_parse_json_reports_malformed():
    with pytest.raises(IntakeError, match="malformed JSON"):
        intake.parse_json('{"skills": [')


# --- a printed CV loses the scheme; importing it must not cost you a warning ---

@pytest.mark.parametrize("written, expected", [
    ("github.com/ada", "https://github.com/ada"),
    ("linkedin.com/in/ada", "https://linkedin.com/in/ada"),
    ("www.ada.dev", "https://www.ada.dev"),
])
def test_a_bare_link_from_a_printed_cv_gets_its_scheme_back(stub_llm, written, expected):
    stub_llm(json.dumps({"personal": {"name": "Ada", "github": written,
                                      "linkedin": written, "website": written}}))
    personal = intake.from_text("Ada Lovelace, engineer.").profile.personal
    assert personal.github == expected
    assert personal.linkedin == expected
    assert personal.website == expected


def test_a_link_that_already_has_one_is_left_alone(stub_llm):
    stub_llm(json.dumps({"personal": {"name": "Ada", "github": "https://github.com/ada"}}))
    assert intake.from_text("Ada.").profile.personal.github == "https://github.com/ada"


def test_something_that_is_not_a_link_is_not_made_into_one(stub_llm):
    stub_llm(json.dumps({"personal": {"name": "Ada", "website": "ask me"}}))
    assert intake.from_text("Ada.").profile.personal.website == "ask me"


def test_an_imported_cv_no_longer_complains_about_its_own_links(stub_llm):
    """The round trip this tool can cause itself: export, print, re-import."""
    stub_llm(json.dumps({"personal": {"name": "Ada", "surname": "Lovelace",
                                      "email": "ada@example.com",
                                      "github": "github.com/ada"},
                         "experience": [{"position": "Engineer", "company": "Acme"}]}))
    issues = intake.from_text("Ada Lovelace.").profile.report()
    assert not [i for i in issues if "http" in i.message]
