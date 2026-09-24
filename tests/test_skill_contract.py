"""The skill and the Python must keep agreeing with each other.

The prompts used to sit ten lines above the code that consumed them, so drift
was visible. They live in a different tree now, and these tests are what replaces
that proximity.

The assertions on the honesty rules are **ported, not invented**: they are the
same strings the deleted prompt tests asserted against `cv.py` and
`cover_letter.py`. That is the point - the guarantee is continuous across the
transformation, and a reviewer can check it by diffing.
"""

import inspect
import json
import re
from pathlib import Path

import pytest
import yaml

from job_hunter.generate import cover_letter, cv
from job_hunter.jobs.models import Job
from job_hunter.skill import __main__ as dispatcher

SKILL = Path(".claude/skills/prep-apply/SKILL.md")
REFERENCES = SKILL.parent / "references"


def fenced_json(path: Path) -> list[dict]:
    blocks = re.findall(r"```json\n(.*?)```", path.read_text(encoding="utf-8"), re.S)
    return [json.loads(b) for b in blocks]


def frontmatter() -> dict:
    return yaml.safe_load(re.match(r"^---\n(.*?)\n---\n",
                                   SKILL.read_text(encoding="utf-8"), re.S).group(1))


# --- the shapes Claude is told to write are the shapes Python reads ---------

def test_the_cv_shape_is_exactly_what_assemble_reads():
    shape, = fenced_json(REFERENCES / "cv-tailoring.md")
    source = inspect.getsource(cv.assemble)
    read = {key for key in ("summary", "roles", "projects", "skills")
            if f'"{key}"' in source or f"'{key}'" in source}
    assert set(shape) == read, "the documented shape and the code have drifted apart"


def test_the_letter_shape_is_exactly_what_assemble_reads():
    shape, = fenced_json(REFERENCES / "cover-letter.md")
    source = inspect.getsource(cover_letter.assemble)
    read = {key for key in ("greeting", "paragraphs", "closing")
            if f'"{key}"' in source}
    assert set(shape) == read


def test_the_job_shape_names_only_real_job_fields():
    shape, = fenced_json(REFERENCES / "job-extraction.md")
    unknown = set(shape) - set(Job.model_fields)
    assert not unknown, f"job-extraction.md documents fields Job does not have: {unknown}"


def test_the_outreach_shape_matches_what_the_verb_reads():
    shape, = fenced_json(REFERENCES / "outreach.md")
    assert set(shape) == {"targets", "message"}
    assert set(shape["message"]) == {"subject", "note", "inmail"}
    assert {t["tier"] for t in shape["targets"]} <= {"alumni", "peer", "manager",
                                                     "recruiter"}


# --- the honesty rules survived the port ------------------------------------

@pytest.mark.parametrize("phrase", [
    "Do not add employers",
    "Never restate a requirement",
    "never add anything",
    "Shorten rather than embellish",
])
def test_the_tailoring_rules_are_still_there(phrase):
    assert phrase in (REFERENCES / "cv-tailoring.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("phrase", [
    "No flattery",
    "Never write a placeholder",
    "language of the posting",
    "Never add one",
])
def test_the_letter_rules_are_still_there(phrase):
    assert phrase in (REFERENCES / "cover-letter.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("phrase", ["Never invent", "Do not infer a salary"])
def test_the_extraction_rules_are_still_there(phrase):
    assert phrase in (REFERENCES / "job-extraction.md").read_text(encoding="utf-8")


def test_nothing_still_tells_the_model_to_return_json_to_a_caller():
    """The one sentence the port was allowed to change, changed everywhere."""
    for path in REFERENCES.glob("*.md"):
        assert "Return only JSON" not in path.read_text(encoding="utf-8"), path.name


# --- the skill and the dispatcher agree -------------------------------------

def test_the_frontmatter_is_readable_and_names_the_argument():
    meta = frontmatter()
    assert meta["name"] == "prep-apply"
    assert meta["arguments"] == ["url"]
    assert "$url" in SKILL.read_text(encoding="utf-8")


def test_it_asks_for_no_tool_it_does_not_need():
    allowed = frontmatter()["allowed-tools"]
    assert "Edit" not in allowed, "the skill never edits; withholding Edit is the point"
    assert "WebFetch" not in allowed, "fetching is Python's job - boards need a browser"


def test_every_verb_the_skill_runs_exists():
    body = SKILL.read_text(encoding="utf-8")
    used = set(re.findall(r"python -m job_hunter\.skill (\w+)", body))
    assert used <= set(dispatcher.VERBS), f"SKILL.md runs verbs that do not exist: "\
                                          f"{used - set(dispatcher.VERBS)}"


def test_every_reference_the_skill_names_exists():
    body = SKILL.read_text(encoding="utf-8")
    named = set(re.findall(r"references/([\w-]+\.md)", body))
    missing = {name for name in named if not (REFERENCES / name).exists()}
    assert not missing, f"SKILL.md points at files that are not there: {missing}"


def test_the_exit_codes_in_the_table_are_the_ones_the_code_uses():
    from job_hunter.skill import exits
    body = SKILL.read_text(encoding="utf-8")
    table = body[body.index("## What the exit codes mean"):]
    for code in (exits.OK, exits.BLOCKED, exits.UNFIT, exits.UNREADABLE):
        assert f"| {code} |" in table, f"exit code {code} is not documented"


def test_the_prohibition_that_holds_the_guarantee_up_is_stated():
    """If a model writes cv.md, the employers and dates come back to it."""
    body = SKILL.read_text(encoding="utf-8")
    assert "Never writes `cv.md` or `letter.md` yourself" in body


# --- the vendor-neutral entry points ----------------------------------------
#
# Four documents now describe the same thing to different audiences, which is
# four chances for them to disagree. These are what keep them honest.

AGENTS = Path("AGENTS.md")
CLAUDE = Path("CLAUDE.md")
COPILOT = Path(".github/copilot-instructions.md")


def test_every_entry_point_exists():
    for path in (AGENTS, CLAUDE, COPILOT, SKILL):
        assert path.exists(), f"{path} is how a whole class of agent finds this repo"


def test_agents_md_points_at_files_that_are_really_there():
    body = AGENTS.read_text(encoding="utf-8")
    named = set(re.findall(r"`?\.claude/skills/prep-apply/[\w/.-]+`?", body))
    missing = [n for n in (x.strip("`") for x in named) if not Path(n).exists()]
    assert not missing, f"AGENTS.md points at files that are not there: {missing}"


def test_agents_md_runs_only_verbs_that_exist():
    used = set(re.findall(r"`(\w+) --run|^\| \d+ \| `(\w+)",
                          AGENTS.read_text(encoding="utf-8"), re.M))
    named = {v for pair in used for v in pair if v}
    assert named <= set(dispatcher.VERBS), \
        f"AGENTS.md runs verbs that do not exist: {named - set(dispatcher.VERBS)}"


def test_the_exit_codes_agree_across_both_entry_points():
    """A harness acting on the wrong code retries what will never work."""
    from job_hunter.skill import exits
    for code in (exits.OK, exits.BLOCKED, exits.UNFIT, exits.UNREADABLE):
        assert f"| {code} |" in AGENTS.read_text(encoding="utf-8")
        assert f"| {code} |" in SKILL.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", [AGENTS, COPILOT])
def test_the_prohibition_that_holds_the_guarantee_up_is_everywhere(path):
    """If any harness writes cv.md itself, the employers go back to a model."""
    assert "cv.md" in path.read_text(encoding="utf-8")


def test_no_entry_point_promises_an_api_key_is_needed():
    """The whole point for this audience: the harness is the model."""
    assert "no API key" in AGENTS.read_text(encoding="utf-8").lower() \
        or "There is **no API key**" in AGENTS.read_text(encoding="utf-8")


def test_the_cross_links_between_them_resolve():
    pairs = [(CLAUDE, "AGENTS.md"), (COPILOT, "AGENTS.md"),
             (AGENTS, "CLAUDE.md")]
    for source, target in pairs:
        assert target in source.read_text(encoding="utf-8"), \
            f"{source} should send readers to {target}"
    # Copilot's file sits in .github/, so its link has to climb out.
    assert "../AGENTS.md" in COPILOT.read_text(encoding="utf-8")


def test_the_skill_body_holds_no_harness_specific_tool_call():
    """Another agent reads SKILL.md too, so it must not assume Claude's tools.

    The frontmatter may - it is Claude-only and AGENTS.md says to skip it.
    """
    body = SKILL.read_text(encoding="utf-8")
    body = body[body.index("---", 3) + 3:]          # drop the frontmatter
    for tool in ("WebFetch(", "Bash(", "Glob("):
        assert tool not in body, f"the procedure calls {tool} directly"
