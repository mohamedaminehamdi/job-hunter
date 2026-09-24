"""The site, and the download archives it hands out.

The page is generated from the skills themselves, so the thing worth testing
is that it cannot drift from them: no skill missing from the page, no download
link pointing at an archive that was never built, no command printed that the
installer would reject.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
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
    assert set(data.CARDS) == set(SKILLS)


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
    for promise in ("applies to nothing", "no api key", "scrape linkedin",
                    "never leaves your machine"):
        assert promise in page.lower(), promise


# --- the motion, in a real browser -----------------------------------------
#
# Static HTML cannot show whether the scroll effects work, and they are the
# part of this page most likely to break silently - an animation that never
# fires leaves content invisible. These drive a real browser.

CORE = ROOT / "core"
sys.path.insert(0, str(CORE))
import jobhunt as jh  # noqa: E402

needs_browser = pytest.mark.skipif(jh.find_browser() is None,
                                   reason="no Chromium-family browser")


def in_browser(probe_js, width=1280, still=False):
    """Run `probe_js` in the built page and return what it wrote to #measured.

    `still` forces prefers-reduced-motion, which is what some CI runners report
    by default - so both branches get exercised on every machine rather than
    whichever one the runner happens to pick.
    """
    page = PAGE.read_text(encoding="utf-8").replace('data-theme=""', 'data-theme="light"')
    work = Path(tempfile.mkdtemp(prefix="jobhunt-probe-"))
    try:
        (work / "page.html").write_text(
            page.replace("</body>", f"<script>{probe_js}</script></body>"),
            encoding="utf-8")
        dump = work / "dom.html"
        command = [jh.find_browser(), "--headless=new", "--disable-gpu",
                   "--no-sandbox", "--no-first-run", "--disable-extensions",
                   f"--window-size={width},1057", f"--user-data-dir={work / 'p'}",
                   "--virtual-time-budget=9000", "--dump-dom"]
        if still:
            command.append("--force-prefers-reduced-motion")
        command.append((work / "page.html").as_uri())
        with dump.open("wb") as sink:
            process = subprocess.Popen(command, stdout=sink, stderr=subprocess.DEVNULL)
        raw = jh._await_file(dump, process, 60, ready=jh._dom_complete)
        jh._stop(process)
        body = raw.decode("utf-8", "replace")
        start = body.find('<pre id="measured"')
        assert start > 0, "the probe never wrote its result"
        return body[body.index(">", start) + 1:body.index("</pre>", start)]
    finally:
        shutil.rmtree(work, ignore_errors=True)


REPORT = """
  var pre = document.createElement('pre');
  pre.id = 'measured';
  pre.textContent = out.join(String.fromCharCode(10));
  document.body.appendChild(pre);
"""


@needs_browser
def test_the_page_throws_nothing():
    """One uncaught error and the arrivals never fire, which means a page with
    invisible sections rather than a visible bug."""
    got = in_browser("""
      window.__errs = [];
      window.addEventListener('error', function (e) {
        window.__errs.push((e.message || '?') + ' @' + e.lineno);
      });
      setTimeout(function () {
        var out = ['errors=' + (window.__errs.length ? window.__errs.join('|') : 'none')];
      """ + REPORT + "}, 400);")
    assert "errors=none" in got, got


@needs_browser
def test_the_first_screenful_is_visible_at_rest():
    """`.up` starts at opacity 0 and is revealed by an observer. If that never
    fires the page is blank - which looks like a broken site rather than a
    broken script, so nobody reports it. This is that failure, caught.

    Only the first screenful: what happens further down depends on scrolling,
    and `test_the_rail_fills_and_lights_the_steps` proves that machinery works.
    """
    got = in_browser("""(function () {
      setTimeout(function () {
        // Transitions off before reading: under virtual time the .7s fade has
        // not advanced, so a mid-transition 0 would look like a broken page.
        // What is being asked is where the opacity *settles*.
        var kill = document.createElement('style');
        kill.textContent = '*{transition:none!important;animation:none!important}';
        document.head.appendChild(kill);
        void document.body.offsetHeight;

        var out = ['js=' + /(^| )js( |$)/.test(document.documentElement.className)];
        ['h1', '.lede', '.cta', '.eyebrow'].forEach(function (sel) {
          var el = document.querySelector(sel);
          out.push(sel + '=' + (el ? getComputedStyle(el).opacity : 'MISSING'));
        });
        out.push('arrived=' + document.querySelectorAll('.in').length);
      """ + REPORT + """ }, 900);
    })();""")
    assert "js=true" in got, got
    for line in got.strip().splitlines():
        if "=" in line and line.split("=")[0] in ("h1", ".lede", ".cta", ".eyebrow"):
            assert line.endswith("=1"), f"{line} - the hero is invisible\n{got}"
    assert "arrived=0" not in got, got


@needs_browser
def test_the_two_numbers_fill_in_when_you_reach_them():
    """The score bars are the one piece of motion carrying real information.

    Scrolled to first: whether the card is on screen at load depends on the
    viewport, and assuming it was cost a CI run. They fill when you get there,
    which is the behaviour - not when the page opens.
    """
    got = in_browser("""(function () {
      var proof = document.querySelector('.proof');
      window.scrollTo({ top: proof.getBoundingClientRect().top + window.scrollY - 200,
                        behavior: 'instant' });
      setTimeout(function () {
        var out = Array.prototype.map.call(
          document.querySelectorAll('.score-bar i'),
          function (i, n) { return 'bar' + n + '=' + (i.style.width || 'unset'); });
      """ + REPORT + """ }, 800);
    })();""")
    assert "unset" not in got, f"the bars never filled\n{got}"
    assert "=0%" not in got, f"the bars filled to nothing\n{got}"


@needs_browser
def test_the_rail_fills_as_you_scroll_the_steps():
    """More of the rail, and more lit badges, the further down you are.

    A relationship rather than two numbers: the fill is a fraction of the
    viewport height, so exact values differ between a laptop and a CI runner -
    which is how this test first failed, asserting 0% where one runner
    computed 4.8%. And where the runner asks for reduced motion the rail is
    deliberately never touched: every step is lit from the start, and that is
    the right answer, not a failure.
    """
    got = in_browser("""(function () {
      var steps = document.querySelector('.steps');
      var rail = steps.querySelector('.rail i');
      var anchor = steps.getBoundingClientRect().top + window.scrollY;
      var out = ['reduced=' +
                 window.matchMedia('(prefers-reduced-motion: reduce)').matches];
      function at(offset, label, then) {
        // instant: the page sets scroll-behavior smooth, which animates over
        // ~500ms and swallows a scripted jump.
        window.scrollTo({ top: Math.max(0, anchor + offset - window.innerHeight * 0.62),
                          behavior: 'instant' });
        window.dispatchEvent(new Event('scroll'));
        setTimeout(function () {
          out.push(label + '=' + parseFloat(rail.style.height || 0) +
                   ',' + steps.querySelectorAll('.step.lit').length);
          then();
        }, 400);
      }
      setTimeout(function () {
        at(-600, 'above', function () {
          at(300, 'into', function () {
            at(4000, 'past', function () {
      """ + REPORT + """ }); }); }); }, 300);
    })();""")
    read = dict(pair.split("=", 1) for pair in got.split() if "=" in pair)
    steps = [tuple(float(n) for n in read[k].split(",")) for k in ("above", "into", "past")]

    if read["reduced"] == "true":
        # Nothing animates, so everything is shown at once. That is the point.
        assert all(lit == 4 for _, lit in steps), got
        return

    (top_fill, top_lit), (mid_fill, mid_lit), (end_fill, end_lit) = steps
    assert top_fill < mid_fill < end_fill, f"the rail does not fill\n{got}"
    assert top_lit <= mid_lit < end_lit, f"the badges do not light\n{got}"
    assert end_fill == 100 and end_lit == 4, f"it never completes\n{got}"


@needs_browser
def test_the_install_routes_are_readable_without_javascript():
    """A page that needs JS to say how to install it fails the person on a
    locked-down machine - who is exactly the person downloading a zip.

    Checked by computing `display` in a real browser rather than by looking
    for the rule: the blanket `[hidden] { display: none !important }` beat the
    override once already, and the CSS text looked perfectly correct.
    """
    got = in_browser("""(function () {
      setTimeout(function () {
        // What a visitor with no script sees. Overwritten rather than
        // regexed away: a backslash-b in a Python string is a backspace,
        // so the regex first written here matched nothing and the probe
        // measured the scripted page while reporting on the other one.
        document.documentElement.className = '';
        void document.body.offsetHeight;
        var panels = document.querySelectorAll('.agent-panel');
        var shown = 0, named = 0;
        Array.prototype.forEach.call(panels, function (p) {
          if (getComputedStyle(p).display !== 'none') shown++;
          var name = p.querySelector('.panel-name');
          if (name && getComputedStyle(name).display !== 'none') named++;
        });
        var empty = document.getElementById('panel-empty');
        var out = ['panels=' + panels.length, 'shown=' + shown, 'named=' + named,
                   'placeholder=' + getComputedStyle(empty).display,
                   'commands=' + document.querySelectorAll('.cmd code').length,
                   'htmlclass=' + JSON.stringify(document.documentElement.className),
                   'nojs=' + document.documentElement.matches('html:not(.js)')];
      """ + REPORT + """ }, 400);
    })();""")
    numbers = dict(pair.split("=", 1) for pair in got.split() if "=" in pair)
    assert numbers["shown"] == numbers["panels"], f"only {numbers['shown']} routes shown\n{got}"
    assert numbers["named"] == numbers["panels"], "the routes are not labelled by agent"
    assert numbers["placeholder"] == "none", "the 'choose an agent' placeholder is still there"
    assert int(numbers["commands"]) >= 8, got


@needs_browser
def test_reduced_motion_shows_everything_at_once():
    """Somebody who asked their machine for less movement gets no movement -
    and, more importantly, still gets the whole page. A CI runner reports this
    preference by default, which is how the branch got exercised at all."""
    got = in_browser("""(function () {
      setTimeout(function () {
        var kill = document.createElement('style');
        kill.textContent = '*{transition:none!important;animation:none!important}';
        document.head.appendChild(kill);
        void document.body.offsetHeight;
        var hidden = 0;
        Array.prototype.forEach.call(document.querySelectorAll('.up, .stagger'),
          function (el) { if (getComputedStyle(el).opacity === '0') hidden++; });
        var out = ['reduced=' +
                     window.matchMedia('(prefers-reduced-motion: reduce)').matches,
                   'invisible=' + hidden,
                   'lit=' + document.querySelectorAll('.step.lit').length,
                   'bars=' + Array.prototype.filter.call(
                     document.querySelectorAll('.score-bar i'),
                     function (i) { return i.style.width; }).length];
      """ + REPORT + """ }, 500);
    })();""", still=True)
    assert "reduced=true" in got, f"the flag did not take\n{got}"
    assert "invisible=0" in got, f"reduced motion hid the page\n{got}"
    assert "lit=4" in got, f"the steps never light\n{got}"
    assert "bars=2" in got, f"the numbers never fill\n{got}"
