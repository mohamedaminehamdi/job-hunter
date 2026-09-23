
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


def test_a_cv_is_not_a_profile(tmp_path):
    """Reading a CV needs a model; this module deliberately has none."""
    cv = tmp_path / "cv.pdf"
    cv.write_bytes(b"%PDF-1.4 whatever")
    with pytest.raises(IntakeError, match="is a CV, not a profile"):
        intake.from_file(cv)


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