"""The site, and the download archives it hands out.

The page is generated from the skills themselves, so the thing worth testing
is that it cannot drift from them: no skill missing from the page, no download
link pointing at an archive that was never built, no command printed that the
installer would reject.
"""

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PAGE = DOCS / "index.html"
DOWNLOAD = DOCS / "download"
SKILLS = sorted(p.name for p in (ROOT / "plugins" / "jobhunt" / "skills").iterdir()
                if p.is_dir())


@pytest.fixture(scope="module")
def page():
    if not PAGE.exists():
        pytest.skip("run python tools/build_site.py")
    return PAGE.read_text(encoding="utf-8")


def tool(name, *args):
    return subprocess.run([sys.executable, str(ROOT / "tools" / name), *args],
                          capture_output=True, text=True, cwd=str(ROOT))


# --- generated, and therefore never stale ----------------------------------

def test_the_page_is_up_to_date():
    done = tool("build_site.py", "--check")
    assert done.returncode == 0, done.stderr


def test_the_archives_are_up_to_date():
    done = tool("build_archives.py", "--check")
    assert done.returncode == 0, done.stderr


def test_building_twice_produces_identical_archives():
    """Otherwise every build is a diff and --check means nothing."""
    before = {p.name: p.read_bytes() for p in DOWNLOAD.glob("*.zip")}
    assert tool("build_archives.py").returncode == 0
    after = {p.name: p.read_bytes() for p in DOWNLOAD.glob("*.zip")}
    assert before == after


def test_a_new_skill_cannot_be_forgotten():
    """data.py lists the display order by hand; the build refuses to guess."""
    sys.path.insert(0, str(ROOT / "tools" / "site"))
    import data
    assert set(data.ORDER) == set(SKILLS)
    assert set(data.HEADLINES) == set(SKILLS)
    assert set(data.PLAIN) == set(SKILLS)


# --- the page describes what actually ships --------------------------------

def test_every_skill_has_a_card(page):
    for skill in SKILLS:
        assert f">{skill}<" in page, f"{skill} is not on the page"


def test_every_download_link_points_at_an_archive_that_exists(page):
    links = set(re.findall(r'href="(download/[^"]+)"', page))
    assert links, "the page offers no downloads"
    for link in links:
        assert (DOCS / link).exists(), f"{link} is linked but was never built"


def test_every_skill_can_be_downloaded_on_its_own(page):
    for skill in SKILLS:
        assert f'href="download/{skill}.zip"' in page, skill


def test_the_page_offers_no_skill_that_does_not_exist(page):
    """Scoped to where a skill is actually named to the reader - a download
    link or the id shown on a card. `jobhunt-agent` in the script is a storage
    key, not a claim about what ships."""
    offered = set(re.findall(r'href="download/([a-z-]+)\.zip"', page))
    offered |= set(re.findall(r'<span class="id">([a-z-]+)</span>', page))
    assert offered, "the page names no skills at all"
    for name in offered - {"jobhunt-all"}:
        assert name in SKILLS, f"the page offers {name}, which does not exist"


# --- the archives are usable ------------------------------------------------

@pytest.mark.parametrize("skill", SKILLS)
def test_each_archive_holds_one_complete_skill(skill):
    archive = DOWNLOAD / f"{skill}.zip"
    assert archive.exists(), "run python tools/build_archives.py"
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
    assert f"{skill}/SKILL.md" in names
    scripts = [n for n in names if n.endswith(".py") and "/lib/" not in n]
    if scripts:
        assert f"{skill}/lib/jobhunt.py" in names, "a script with no library"
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)


def test_the_all_archive_holds_every_skill():
    with zipfile.ZipFile(DOWNLOAD / "jobhunt-all.zip") as zf:
        names = zf.namelist()
    for skill in SKILLS:
        assert f"{skill}/SKILL.md" in names, skill


def test_a_downloaded_skill_runs(tmp_path):
    """The whole promise of the download route, tested by doing it."""
    import os
    with zipfile.ZipFile(DOWNLOAD / "jobhunt-guard.zip") as zf:
        zf.extractall(tmp_path)
    done = subprocess.run(
        [sys.executable, str(tmp_path / "jobhunt-guard" / "guard.py"), "--help"],
        capture_output=True, text=True, cwd=str(tmp_path),
        env={"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path)})
    assert done.returncode == 0, done.stderr
    assert "usage:" in done.stdout


def test_the_manifest_matches_the_archives():
    manifest = json.loads((DOWNLOAD / "manifest.json").read_text())
    for name, entry in manifest.items():
        path = DOWNLOAD / entry["file"]
        assert path.exists() and path.stat().st_size == entry["bytes"], name


# --- the page holds together -----------------------------------------------

def test_it_is_one_self_contained_file_plus_the_archives(page):
    """GitHub Pages serves it flat: no build step, no bundler, no assets to 404."""
    # Fonts and the repo link. Nothing else: an asset that 404s on a fork or
    # behind a firewall would take the styling with it.
    allowed = ("https://fonts.googleapis.com", "https://fonts.gstatic.com",
               "https://github.com/")
    for url in set(re.findall(r'(?:src|href)="(https?://[^"]+)"', page)):
        assert url.startswith(allowed), url
    assert '<link rel="stylesheet" href="style' not in page  # CSS is inlined
    assert "<script src=" not in page                        # JS is inlined


def test_nothing_is_hidden_behind_javascript(page):
    """A page that needs JS to say how to install it fails the person on a
    locked-down machine - who is exactly the person downloading a zip."""
    assert "html:not(.js) .agent-panel[hidden] { display: block; }" in page
    assert "[hidden] { display: none !important; }" in page


def test_both_themes_define_every_colour(page):
    css = page.split("<style>", 1)[1].split("</style>")[0]
    light = set(re.findall(r"(--[a-z-]+):", css.split("@media")[0]))
    for block in ("@media (prefers-color-scheme: dark)", ':root[data-theme="dark"]'):
        assert block in css
    # every token redefined in dark must exist in light, or the light theme has a hole
    dark = set(re.findall(r"(--[a-z-]+):", css.split(':root[data-theme="dark"]')[1]))
    assert dark <= light, dark - light


def test_the_page_says_what_it_will_not_do(page):
    """The claims that make this tool worth using have to survive a redesign."""
    for promise in ("apply to nothing", "No API key", "scrape LinkedIn"):
        assert promise.lower() in page.lower(), promise
