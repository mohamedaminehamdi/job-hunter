import pytest

from job_hunter.generate import parsing
from job_hunter.generate.parsing import ParseError


def test_plain_json():
    assert parsing.parse_json('{"a": 1}') == {"a": 1}


def test_code_fence():
    assert parsing.parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_prose_around_json():
    assert parsing.parse_json('Sure!\n{"a": 1}\nLet me know.') == {"a": 1}


def test_nested_braces_survive_salvage():
    raw = 'Here you go:\n{"a": {"b": [1, 2]}}\ndone'
    assert parsing.parse_json(raw) == {"a": {"b": [1, 2]}}


def test_non_object_rejected():
    with pytest.raises(ParseError, match="not a list"):
        parsing.parse_json("[1, 2]")


def test_no_json_at_all():
    with pytest.raises(ParseError, match="did not return JSON"):
        parsing.parse_json("I can't help with that.")


def test_truncated_response_named_as_such():
    with pytest.raises(ParseError, match="cut off"):
        parsing.parse_json('{"a": [1, 2')


def test_malformed_json_reports_the_decode_error():
    with pytest.raises(ParseError, match="malformed JSON"):
        parsing.parse_json('{"a": 1,, }')


def test_hint_is_appended_to_advice_errors():
    with pytest.raises(ParseError, match="paste it as YAML"):
        parsing.parse_json("nope", hint="Try again, or paste it as YAML.")


def test_hint_absent_by_default():
    with pytest.raises(ParseError) as caught:
        parsing.parse_json("nope")
    assert str(caught.value) == "The model did not return JSON."
