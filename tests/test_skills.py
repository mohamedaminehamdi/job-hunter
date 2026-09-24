"""The skills as shipped: do they hold together, and does each run alone?

Everything here is about the packaging rather than the behaviour. The library
is tested elsewhere; what these check is that eleven copies of it stay in step,
that every SKILL.md says something true about the script beside it, and that a
skill installed on its own - no repo, no siblings, nothing on sys.path - still
works.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins" / "jobhunt" / "skills"
CORE = ROOT / "core" / "jobhunt.py"

ALL = sorted(p for p in SKILLS.iterdir() if p.is_dir())
WITH_SCRIPT = [p for p in ALL if list(p.glob("*.py"))]


def script_of(skill):
    found = list(skill.glob("*.py"))
    return found[0] if found else None


def frontmatter(skill):
    """The YAML block at the top of a SKILL.md, read with our own reader."""
    sys.path.insert(0, str(ROOT / "core"))
    import jobhunt as jh
    body = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert body.startswith("---\n"), f"{skill.name}: no frontmatter"
    return jh.yaml_load(body.split("---\n", 2)[1])


# --- the eleven exist and are described ------------------------------------

def test_there_are_eleven_skills():
    assert len(ALL) == 11, [p.name for p in ALL]


@pytest.mark.parametrize("skill", ALL, ids=lambda p: p.name)
def test_every_skill_has_a_skill_md_naming_itself(skill):
    got = frontmatter(skill)
    assert got["name"] == skill.name, f"{got['name']!r} in {skill.name}/"


@pytest.mark.parametrize("skill", ALL, ids=lambda p: p.name)
def test_every_description_says_when_to_use_it(skill):
    """The description is the only thing an agent sees before loading a skill.

    A description that only says what the skill *is* never gets picked, so each
    one has to name the situation as well.
    """
    description = " ".join(frontmatter(skill)["description"].split())
    assert 60 < len(description) <= 500, f"{skill.name}: {len(description)} chars"
    assert "Use " in description or "use when" in description.lower(), skill.name


@pytest.mark.parametrize("skill", WITH_SCRIPT, ids=lambda p: p.name)
def test_every_skill_md_names_the_script_beside_it(skill):
    body = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert script_of(skill).name in body, f"{skill.name}: SKILL.md never runs its script"


# --- the copies do not drift ------------------------------------------------

@pytest.mark.parametrize("skill", WITH_SCRIPT, ids=lambda p: p.name)
def test_the_library_copy_matches_the_source(skill):
    """`tools/sync.py` is the only thing allowed to write these."""
    copy = skill / "lib" / "jobhunt.py"
    assert copy.exists(), f"{skill.name}: run python tools/sync.py"
    assert copy.read_text(encoding="utf-8").endswith(CORE.read_text(encoding="utf-8")), \
        f"{skill.name}/lib/jobhunt.py is out of date - run python tools/sync.py"


def test_sync_check_agrees():
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "sync.py"), "--check"],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize("skill", WITH_SCRIPT, ids=lambda p: p.name)
def test_a_script_imports_only_its_own_copy(skill):
    """No skill may import from a sibling: they are installed one at a time."""
    source = script_of(skill).read_text(encoding="utf-8")
    assert "lib" in source and "sys.path.insert" in source
    for other in WITH_SCRIPT:
        if other != skill:
            assert other.name not in source, f"{skill.name} refers to {other.name}"


# --- installed on its own ---------------------------------------------------

@pytest.mark.parametrize("skill", WITH_SCRIPT, ids=lambda p: p.name)
def test_a_script_runs_with_nothing_else_present(skill, tmp_path):
    """Copy one skill somewhere empty and run it. No repo, no siblings, no path.

    This is the whole premise - somebody downloads one folder - so it is tested
    the way it will actually happen rather than by importing the module.
    """
    import shutil
    alone = tmp_path / skill.name
    shutil.copytree(skill, alone)

    empty = tmp_path / "elsewhere"
    empty.mkdir()
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(empty),
           "JOBHUNT_HOME": str(empty / "jobhunt")}

    done = subprocess.run([sys.executable, str(alone / script_of(skill).name), "--help"],
                          capture_output=True, text=True, cwd=empty, env=env)
    assert done.returncode == 0, f"{skill.name}: {done.stderr[-400:]}"
    assert "usage:" in done.stdout


# --- the manifests ----------------------------------------------------------

def test_the_marketplace_points_at_a_plugin_that_exists():
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    for entry in market["plugins"]:
        target = (ROOT / entry["source"]).resolve()
        assert (target / ".claude-plugin" / "plugin.json").exists(), entry["source"]


def test_the_plugin_and_the_marketplace_agree_on_the_version():
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    plugin = json.loads(
        (ROOT / "plugins" / "jobhunt" / ".claude-plugin" / "plugin.json").read_text())
    assert market["plugins"][0]["version"] == plugin["version"]


def test_both_vendors_get_a_manifest():
    """Claude Code reads .claude-plugin, Codex reads .codex-plugin.

    Same folder, two names. Checked against a real installed Codex plugin
    rather than guessed at.
    """
    plugin = ROOT / "plugins" / "jobhunt"
    for vendor in (".claude-plugin", ".codex-plugin"):
        assert (plugin / vendor / "plugin.json").exists(), vendor


def test_the_two_manifests_agree():
    plugin = ROOT / "plugins" / "jobhunt"
    claude = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text())
    codex = json.loads((plugin / ".codex-plugin" / "plugin.json").read_text())
    for field in ("name", "version", "license", "repository", "homepage"):
        assert claude[field] == codex[field], field


def test_the_codex_manifest_points_at_the_skills():
    codex = json.loads((ROOT / "plugins" / "jobhunt" / ".codex-plugin"
                        / "plugin.json").read_text())
    assert (ROOT / "plugins" / "jobhunt" / codex["skills"]).resolve() == SKILLS


def test_the_plugin_version_matches_the_library():
    sys.path.insert(0, str(ROOT / "core"))
    import jobhunt as jh
    plugin = json.loads(
        (ROOT / "plugins" / "jobhunt" / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["version"] == jh.VERSION
