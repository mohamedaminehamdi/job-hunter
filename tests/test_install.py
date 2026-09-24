"""The installer, run the way a person runs it.

This is the first thing a non-engineer executes and the only part of the
project that deletes files, so it is tested against a real HOME with real
copies rather than by reading the script.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "install.sh"
SKILLS = sorted(p.name for p in (ROOT / "plugins" / "jobhunt" / "skills").iterdir()
                if p.is_dir())


def run(home, *args, cwd=None):
    return subprocess.run(
        ["sh", str(INSTALL), *args], capture_output=True, text=True,
        cwd=str(cwd or ROOT),
        env={"PATH": os.environ.get("PATH", ""), "HOME": str(home), "NO_COLOR": "1"})


@pytest.fixture
def home(tmp_path):
    where = tmp_path / "home"
    (where / ".claude").mkdir(parents=True)
    (where / ".codex").mkdir(parents=True)
    return where


# --- it does what it says --------------------------------------------------

def test_it_installs_into_every_agent_it_finds(home):
    done = run(home, "--only", "jobhunt-guard")
    assert done.returncode == 0, done.stderr
    for agent in (".claude", ".codex"):
        assert (home / agent / "skills" / "jobhunt-guard" / "guard.py").exists()
        assert (home / agent / "skills" / "jobhunt-guard" / "lib" / "jobhunt.py").exists()


def test_all_eleven_install(home):
    assert run(home).returncode == 0
    assert sorted(p.name for p in (home / ".claude" / "skills").iterdir()) == SKILLS


def test_list_changes_nothing(home):
    done = run(home, "--list")
    assert done.returncode == 0
    assert "Would install" in done.stdout
    assert not list((home / ".claude" / "skills").iterdir()) \
        if (home / ".claude" / "skills").exists() else True


def test_uninstall_removes_only_the_skills(home):
    run(home)
    marker = home / ".claude" / "skills" / "keep-me.txt"
    marker.write_text("not ours")
    assert run(home, "--uninstall").returncode == 0
    assert marker.exists(), "uninstall took something that was not ours"
    assert not (home / ".claude" / "skills" / "jobhunt-guard").exists()


def test_reinstalling_replaces_rather_than_merges(home):
    """A file left behind from an older version is worse than a missing one."""
    run(home, "--only", "jobhunt-guard")
    stale = home / ".claude" / "skills" / "jobhunt-guard" / "old-helper.py"
    stale.write_text("# from a previous version")
    run(home, "--only", "jobhunt-guard")
    assert not stale.exists()


# --- it says no clearly ----------------------------------------------------

def test_an_unknown_skill_name_is_refused_with_the_list(home):
    done = run(home, "--only", "jobhunt-nope")
    assert done.returncode == 1
    assert "no skill called 'jobhunt-nope'" in done.stderr
    assert "jobhunt-guard" in done.stderr  # it says what there is


def test_no_agent_found_explains_the_project_route(tmp_path):
    done = run(tmp_path / "bare")
    assert "No coding agent found" in done.stderr
    assert "--to .cursor" in done.stdout


def test_a_destination_it_cannot_write_fails_loudly(home, tmp_path):
    """The bug this catches: a `while read` fed by a pipe runs in a subshell,
    so `die` killed the subshell and the script went on to print success."""
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        done = run(home, "--to", str(locked / "x"), "--only", "jobhunt-guard")
        assert done.returncode != 0, "reported success after failing to install"
    finally:
        locked.chmod(0o700)


# --- the project-level route (Cursor, Cline, Windsurf) ---------------------

def test_to_installs_into_a_project_directory(home, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    done = run(home, "--to", ".cursor", "--only", "jobhunt-guard", cwd=project)
    assert done.returncode == 0, done.stderr
    assert (project / ".cursor" / "skills" / "jobhunt-guard" / "guard.py").exists()
    # and it prints somewhere the reader can actually go and look
    assert str(project) in done.stdout


# --- what it installs actually runs ----------------------------------------

@pytest.mark.parametrize("skill", [s for s in SKILLS
                                   if list((ROOT / "plugins" / "jobhunt" / "skills"
                                            / s).glob("*.py"))])
def test_every_installed_script_runs(home, tmp_path, skill):
    import sys
    run(home)
    script = next((home / ".claude" / "skills" / skill).glob("*.py"))
    work = tmp_path / "work"
    work.mkdir()
    done = subprocess.run([sys.executable, str(script), "--help"],
                          capture_output=True, text=True, cwd=work,
                          env={"PATH": os.environ.get("PATH", ""), "HOME": str(home)})
    assert done.returncode == 0, done.stderr[-300:]


# --- the script itself ------------------------------------------------------

def test_it_passes_shellcheck_as_sh_and_as_bash():
    if shutil.which("shellcheck") is None:
        pytest.skip("shellcheck not installed")
    for shell in ("sh", "dash", "bash"):
        done = subprocess.run(["shellcheck", "-s", shell, str(INSTALL)],
                              capture_output=True, text=True)
        assert done.returncode == 0, f"{shell}:\n{done.stdout}"


def test_it_offers_every_skill_that_exists():
    """A skill added to the repo and forgotten here is a skill nobody installs."""
    body = INSTALL.read_text(encoding="utf-8")
    listed = body.split("SKILLS=", 1)[1].split("\n\n", 1)[0]
    for skill in SKILLS:
        assert skill in listed, f"install.sh never offers {skill}"
