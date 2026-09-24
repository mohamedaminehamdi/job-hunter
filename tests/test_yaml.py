"""The YAML subset.

Every test here is a bug that a comparison against pyyaml actually found on
real files. The subset is small because every field stored as YAML in this
project is a string or a list of strings, so the reader never guesses a type -
but the files it has to read were written by pyyaml, which folds, quotes and
chomps in ways the writer here does not.
"""

import pytest

from jobhunt import YamlError, yaml_dump, yaml_load


def roundtrip(data):
    return yaml_load(yaml_dump(data))


# --- what pyyaml writes and we must read ------------------------------------

def test_a_folded_scalar_joins_with_spaces():
    assert yaml_load("summary: one\n  two\n  three\n") == {"summary": "one two three"}


def test_a_folded_line_containing_a_colon_is_not_a_key():
    """"fleet: we partner on supply deals" is prose. Only the indent says so."""
    got = yaml_load("description: Anthropic runs a fleet\n"
                    "  fleet: we partner on supply deals\n")
    assert got == {"description": "Anthropic runs a fleet fleet: we partner on supply deals"}


def test_a_blank_line_inside_a_fold_is_a_paragraph_break():
    assert yaml_load("text: one\n  two\n\n  three\n") == {"text": "one two\nthree"}


def test_a_dash_that_opens_a_map_is_not_a_fold():
    """"- position: X" then a deeper line is a sibling key, not continuation."""
    got = yaml_load("experience:\n- position: Engineer\n  company: Acme\n")
    assert got == {"experience": [{"position": "Engineer", "company": "Acme"}]}


def test_a_single_quote_inside_single_quotes_is_doubled():
    assert yaml_load("m: '''CV'' is not in your profile'") == {
        "m": "'CV' is not in your profile"}


def test_a_non_breaking_space_is_content_not_whitespace():
    """str.strip() eats \\xa0. YAML strips only space and tab."""
    assert yaml_load("t: ends with one \n  and continues\n") == {
        "t": "ends with one  and continues"}


@pytest.mark.parametrize("indicator, expected", [("|", "a\nb\n"), ("|-", "a\nb")])
def test_a_block_keeps_or_strips_its_last_newline(indicator, expected):
    assert yaml_load(f"t: {indicator}\n  a\n  b\n") == {"t": expected}


def test_a_block_keeps_its_own_leading_whitespace():
    assert yaml_load("t: |\n  a\n    indented\n")["t"] == "a\n  indented\n"


# --- what we write, and what any other reader will make of it ---------------

def test_a_numeric_looking_string_is_quoted_on_the_way_out():
    """Unquoted 2026 comes back from any other YAML reader as an integer."""
    written = yaml_dump({"end": "2026", "grade": "5.5", "ok": "true"})
    assert '"2026"' in written and '"5.5"' in written and '"true"' in written
    assert roundtrip({"end": "2026"}) == {"end": "2026"}


def test_a_value_with_a_colon_is_quoted():
    assert roundtrip({"note": "fleet: we partner"}) == {"note": "fleet: we partner"}


def test_a_long_value_is_never_folded():
    """A folded achievement bullet is what someone then edits wrongly."""
    long = "Cut ETL runtime by 35% " * 12
    assert len([l for l in yaml_dump({"b": long}).splitlines()]) == 1


def test_multi_line_text_round_trips():
    for value in ("a\nb", "a\nb\n", "a\n\nb\n", "  leading", "trailing  "):
        assert roundtrip({"t": value}) == {"t": value}, repr(value)


def test_empty_values_survive():
    assert roundtrip({"a": "", "b": [], "c": {"d": ""}}) == {"a": "", "b": [], "c": {"d": ""}}


def test_a_list_of_maps_round_trips():
    data = {"experience": [{"position": "Engineer", "bullets": ["one", "two"]},
                           {"position": "Analyst", "bullets": []}]}
    assert roundtrip(data) == data


def test_a_flow_list_is_read():
    assert yaml_load("skills: [Python, dbt]") == {"skills": ["Python", "dbt"]}


# --- failure -----------------------------------------------------------------

def test_a_broken_line_says_which_line():
    """The old reader returned an empty profile, so a typo on line 14 was
    reported as 'a name is required'."""
    with pytest.raises(YamlError) as caught:
        yaml_load("personal:\n  name: Ada\n  !! broken\n")
    assert caught.value.line == 3
    assert "line 3" in str(caught.value)


def test_yaml_we_do_not_do_says_so_rather_than_guessing():
    with pytest.raises(YamlError, match="this reader does not do"):
        yaml_load("a: &anchor value\n")


def test_comments_are_dropped_but_not_inside_quotes():
    assert yaml_load("a: one  # note\nb: 'two # three'") == {"a": "one", "b": "two # three"}
