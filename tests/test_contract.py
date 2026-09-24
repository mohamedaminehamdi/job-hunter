"""Where the prose and the code have to agree.

A SKILL.md is instructions for a model. When it drifts from the script beside
it the failure is quiet - the agent writes JSON in a shape nothing reads, or
retries something that will never work - so the places the two touch are
pinned here: the JSON keys, the exit codes, the flags, and the handful of
sentences that hold the honesty guarantee up.
"""

import re
from pathlib import Path

import jobhunt as jh
import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins" / "jobhunt" / "skills"
ALL = sorted(p for p in SKILLS.iterdir() if p.is_dir())


def body(skill):
    return (skill / "SKILL.md").read_text(encoding="utf-8")


def fenced_json(text):
    """Every ```json block, as a dict - that is the shape being promised."""
    import json
    out = []
    for block in re.findall(r"```json\n(.*?)```", text, re.S):
        try:
            out.append(json.loads(block))
        except json.JSONDecodeError:
            pytest.fail(f"a ```json block is not valid JSON:\n{block[:200]}")
    return out


# --- the JSON shapes the skills ask for are the ones the code reads --------

def test_the_posting_shape_names_only_real_job_fields():
    shape, = fenced_json(body(SKILLS / "jobhunt-posting"))
    unknown = set(shape) - jh.fieldnames(jh.Job)
    assert not unknown, f"jobhunt-posting asks for {unknown}, which Job has no room for"


def test_the_tailoring_shape_is_exactly_what_tailor_reads():
    shape, = fenced_json(body(SKILLS / "jobhunt-tailor"))
    assert set(shape) == {"summary", "roles", "projects", "skills"}
    # and a document really does come out of it
    document = jh.tailor(jh.Profile(experience=[jh.Role(company="Acme",
                                                        bullets=["Did work."])]),
                         jh.Job(title="Engineer"), shape)
    assert isinstance(document, jh.TailoredCV)


def test_the_letter_shape_is_exactly_what_write_letter_reads():
    shape, = fenced_json(body(SKILLS / "jobhunt-letter"))
    assert set(shape) == {"greeting", "paragraphs", "closing"}
    letter = jh.write_letter(jh.Profile(), jh.Job(), shape)
    assert letter.greeting == shape["greeting"]


def test_the_outreach_shape_is_exactly_what_plan_outreach_reads():
    shape, = fenced_json(body(SKILLS / "jobhunt-outreach"))
    assert set(shape) == {"targets", "message"}
    assert set(shape["message"]) == set(jh.fieldnames(jh.Message))
    plan = jh.plan_outreach(shape, jh.Profile(), jh.Job(company="Acme"))
    assert len(plan.targets) == len(shape["targets"])


def test_the_tiers_the_outreach_skill_names_are_the_ones_that_exist():
    shape, = fenced_json(body(SKILLS / "jobhunt-outreach"))
    for target in shape["targets"]:
        assert target["tier"] in jh.TIERS, target["tier"]
    for tier in jh.TIERS:
        assert tier in body(SKILLS / "jobhunt-outreach"), f"{tier} is never mentioned"


def test_the_profile_shape_is_one_the_loader_reads():
    """The example in jobhunt-profile is what someone's career gets written into."""
    yaml_block, = re.findall(r"```yaml\n(.*?)```", body(SKILLS / "jobhunt-profile"), re.S)
    profile = jh.build(jh.Profile, jh.yaml_load(yaml_block))
    assert profile.personal.full_name == "Ada Lovelace"
    assert profile.experience and profile.experience[0].bullets
    assert profile.education and profile.projects and profile.certifications
    assert profile.is_renderable


# --- the exit codes ---------------------------------------------------------

def test_the_exit_code_table_matches_the_code():
    table = body(SKILLS / "jobhunt")
    for code in (jh.OK, jh.BLOCKED, jh.UNFIT, jh.UNREADABLE):
        assert f"| `{code}` |" in table, f"exit {code} is not in the table"
    assert f"| `{jh.UNREADABLE + 1}` |" not in table, "the table invents a code"


@pytest.mark.parametrize("skill", [p for p in ALL if list(p.glob("*.py"))],
                         ids=lambda p: p.name)
def test_every_flag_a_skill_md_shows_is_one_its_script_accepts(skill):
    script = next(iter(sorted(skill.glob("*.py")))).read_text(encoding="utf-8")
    for line in body(skill).splitlines():
        if "python3 " not in line:
            continue
        for flag in re.findall(r"\s(--[a-z-]{2,})", line):
            assert f'"{flag}"' in script, f"{skill.name}: SKILL.md shows {flag}"


# --- the sentences that hold the guarantee up ------------------------------

@pytest.mark.parametrize("phrase", [
    "indices",              # the model points at the profile, it does not write it
    "invent",               # said in those words, so it cannot be skimmed past
])
def test_the_tailoring_rule_is_still_stated(phrase):
    assert phrase in body(SKILLS / "jobhunt-tailor").lower()


def test_the_letter_is_still_told_the_posting_is_not_a_source_of_claims():
    text = body(SKILLS / "jobhunt-letter")
    assert "requirements are **not**" in text or "not** a source" in text
    assert "Kafka" in text  # the concrete example, not just the principle


def test_the_prohibition_that_holds_the_guarantee_up_is_in_the_orchestrator():
    """If a model writes cv.md itself, the employers and dates go back to it."""
    text = body(SKILLS / "jobhunt")
    assert "cv.md" in text and "letter.md" in text
    assert "rendered from" in text


def test_no_skill_promises_an_api_key_is_needed():
    """The whole point for this audience: the harness is the model."""
    for skill in ALL:
        text = body(skill).lower()
        for wrong in ("api key is required", "set your api key", "openai_api_key"):
            assert wrong not in text, f"{skill.name} asks for a key"


def test_the_orchestrator_still_refuses_the_four_things():
    text = body(SKILLS / "jobhunt")
    for promise in ("Never applies", "Never scrapes LinkedIn", "Never invents",
                    "Never works around a login wall"):
        assert promise in text, promise


def test_no_skill_assumes_one_vendors_tools():
    """Another agent reads these too, so they must not name Claude's tools in
    the body - only in frontmatter, which each harness reads as it likes."""
    for skill in ALL:
        text = body(skill).split("---", 2)[2]
        for tool in ("WebFetch(", "Bash(", "str_replace_editor", "<function_calls>"):
            assert tool not in text, f"{skill.name} names {tool}"


# --- the run directory both halves agree on --------------------------------

def test_the_files_the_skills_name_are_the_ones_the_scripts_write():
    """A SKILL.md telling the agent to read a file nothing writes is a dead end."""
    written = set()
    for skill in ALL:
        for script in skill.glob("*.py"):
            source = script.read_text(encoding="utf-8")
            written |= set(re.findall(r'write_text\(run, "([^"]+)"', source))
            written |= set(re.findall(r'write_json\(run, "([^"]+)"', source))
            written |= set(re.findall(r'run / "([^"]+\.(?:yaml|md|json))"', source))
            written |= set(re.findall(r'f"fit-\{args\.when\}\.(\w+)"', source))
    # the two written through an f-string
    written |= {"fit-before.json", "fit-after.json", "fit-before.md", "fit-after.md"}
    for name in ("job.yaml", "cv.yaml", "letter.yaml", "outreach.md",
                 "critique.md", "page.txt", "fit-before.md", "fit-after.md"):
        assert name in written, f"nothing writes {name}"
