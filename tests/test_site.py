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


def test_no_element_wears_a_class_the_stylesheet_never_styles(page):
    """A renamed rule leaves the markup pointing at nothing, and the element
    quietly renders as an unstyled box. Eight download buttons were doing
    exactly that after `.btn-quiet` was renamed out from under them.

    Classes used only as JavaScript hooks are listed, because they are real -
    they just do not need a rule.
    """
    hooks = {"js", "in", "stuck", "lit", "i-copy", "i-done", "say"}
    css = page.split("<style>", 1)[1].split("</style>")[0]
    styled = set(re.findall(r"\.([a-zA-Z][\w-]*)", css))

    used = set()
    for attr in re.findall(r'class="([^"]+)"', page):
        used |= set(attr.split())

    orphans = used - styled - hooks
    assert not orphans, f"no rule for: {sorted(orphans)}"


def test_the_glass_has_somewhere_to_fall_back_to(page):
    """`backdrop-filter` is unsupported in places and switched off by anyone
    who asked their machine for less transparency. Without a fallback those
    surfaces become 13%-white rectangles on a dark field - which is to say
    invisible, along with the text on them."""
    css = page.split("<style>", 1)[1].split("</style>")[0]
    assert "@supports not ((backdrop-filter" in css, "no unsupported-browser fallback"
    assert "prefers-reduced-transparency" in css, "no reduced-transparency fallback"
    # and the fallback must actually set a background, not merely exist
    block = css.split("prefers-reduced-transparency", 1)[1][:400]
    assert "background:" in block and "backdrop-filter: none" in block, block


def test_white_text_on_the_field_clears_wcag_aa(page):
    """The field's colours were chosen by this number, so it is worth keeping.
    AA is 4.5:1 for body text; the brightest point of the gradient is what has
    to pass, not the base."""
    css = page.split("<style>", 1)[1].split("</style>")[0]
    lift = re.search(r"--field-lift:\s*(#[0-9a-fA-F]{6})", css).group(1)

    def luminance(colour):
        parts = (int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
        chan = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                for c in parts]
        return 0.2126 * chan[0] + 0.7152 * chan[1] + 0.0722 * chan[2]

    ratio = (1.0 + 0.05) / (luminance(lift) + 0.05)
    assert ratio >= 4.5, f"white on {lift} is {ratio:.2f}:1, below AA"


def test_both_themes_define_every_colour(page):
    css = page.split("<style>", 1)[1].split("</style>")[0]
    light = set(re.findall(r"(--[a-z-]+):", css.split("@media")[0]))
    for block in ("@media (prefers-color-scheme: dark)", ':root[data-theme="dark"]'):
        assert block in css
    # every token redefined in dark must exist in light, or the light theme has a hole
    dark = set(re.findall(r"(--[a-z-]+):", css.split(':root[data-theme="dark"]')[1]))
    assert dark <= light, dark - light


def test_the_page_says_what_it_will_not_do(page):
    """The claims that make this tool worth using have to survive a redesign,
    and they have now survived three."""
    for promise in ("applies to nothing",      # in the footer
                    "never logs in",           # the outreach note
                    "never sends",
                    "nothing to sign up for",  # the install section
                    "not built yet"):          # the roadmap, labelled as one
        assert promise in page.lower(), promise


def test_the_roadmap_is_never_written_as_a_feature(page):
    """Auto-apply is on the page and is not built. A visitor must not be able
    to read it as something that works today - the code refuses to apply, and
    a page that implies otherwise is the one thing here that would be a lie."""
    soon = page.split('id="soon"', 1)[1].split("</div>\n</div>")[0].lower()
    assert "not built yet" in soon or "coming soon" in soon
    # and the claim never appears in the present tense anywhere else
    body = page.lower()
    for wrong in ("applies for you", "submits your application",
                  "applies to jobs for you"):
        assert wrong not in body, wrong


# --- the motion, in a real browser -----------------------------------------
#
# Static HTML cannot show whether the scroll effects work, and they are the
# part of this page most likely to break silently - an animation that never
# fires leaves content invisible rather than visibly wrong, so nobody reports
# it.
#
# One browser launch per configuration, not one per assertion. Six launches
# with virtual-time budgets on a shared runner was slow and flaky enough to
# fail CI on its own, which is worse than not testing this at all.

CORE = ROOT / "core"
sys.path.insert(0, str(CORE))
import jobhunt as jh  # noqa: E402

needs_browser = pytest.mark.skipif(jh.find_browser() is None,
                                   reason="no Chromium-family browser")

#: Everything the probes measure, run in one page load and reported together.
PROBE = r"""
(function () {
  var NL = String.fromCharCode(10);
  var out = [];
  var errs = [];
  window.addEventListener('error', function (e) {
    errs.push((e.message || '?') + ' @' + e.lineno);
  });

  function settle() {
    // Transitions off before measuring: under virtual time a .7s fade has not
    // advanced, so a mid-transition 0 would read as a broken page. What is
    // being asked is where things settle.
    var kill = document.createElement('style');
    kill.textContent = '*{transition:none!important;animation:none!important}';
    document.head.appendChild(kill);
    void document.body.offsetHeight;
  }
  function jump(y) {
    // instant: the page sets scroll-behavior smooth, which animates over
    // ~500ms and swallows a scripted jump.
    window.scrollTo({ top: Math.max(0, y), behavior: 'instant' });
    window.dispatchEvent(new Event('scroll'));
  }
  function done() {
    var pre = document.createElement('pre');
    pre.id = 'measured';
    pre.textContent = out.join(NL);
    document.body.appendChild(pre);
  }

  var steps = document.querySelector('.steps');
  var rail = steps.querySelector('.rail i');
  var anchor = steps.getBoundingClientRect().top + window.scrollY;
  out.push('reduced=' +
           window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  out.push('js=' + /(^| )js( |$)/.test(document.documentElement.className));

  setTimeout(function () {
    // 1. the first screenful, at rest
    settle();
    ['h1', 'cta', 'eyebrow', 'slider'].forEach(function (name) {
      var el = document.querySelector(name === 'h1' ? 'h1' : '.' + name);
      out.push('hero-' + name + '=' + (el ? getComputedStyle(el).opacity : 'MISSING'));
    });
    // Sampled twice, because the first sample is just the text the script
    // seeds before the loop starts - a broken animation passes that.
    var swap = document.querySelector('.type .live');
    out.push('typed=' + (swap ? (swap.textContent || '').length : 'MISSING'));
    window.__typedFirst = swap ? swap.textContent : '';

    // 2. the rail, at three depths
    (function () {
      jump(anchor - 600 - window.innerHeight * 0.62);
      setTimeout(function () {
        out.push('railAbove=' + parseFloat(rail.style.height || 0) + ',' +
                 steps.querySelectorAll('.step.lit').length);
        jump(anchor + 300 - window.innerHeight * 0.62);
        setTimeout(function () {
          out.push('railInto=' + parseFloat(rail.style.height || 0) + ',' +
                   steps.querySelectorAll('.step.lit').length);
          jump(anchor + 4000 - window.innerHeight * 0.62);
          setTimeout(function () {
            out.push('railPast=' + parseFloat(rail.style.height || 0) + ',' +
                     steps.querySelectorAll('.step.lit').length);

            // 4. the install routes with no script at all
            document.documentElement.className = '';
            void document.body.offsetHeight;
            var panels = document.querySelectorAll('.agent-panel');
            var shown = 0, named = 0;
            Array.prototype.forEach.call(panels, function (p) {
              if (getComputedStyle(p).display !== 'none') shown++;
              var name = p.querySelector('.panel-name');
              if (name && getComputedStyle(name).display !== 'none') named++;
            });
            out.push('panels=' + panels.length);
            out.push('nojsShown=' + shown);
            out.push('nojsNamed=' + named);
            out.push('nojsPlaceholder=' +
                     getComputedStyle(document.getElementById('panel-empty')).display);
            out.push('commands=' + document.querySelectorAll('.cmd code').length);

            // The headline holds its first phrase for 2.1s on purpose, so
            // that people can read it. The probe has to outlast that.
            setTimeout(function () {
              var late = document.querySelector('.type .live');
              out.push('typedLater=' +
                       (late ? (late.textContent || '').length : '-'));
              out.push('typedMoved=' +
                       (late ? String(late.textContent !== window.__typedFirst)
                             : '-'));
              out.push('errors=' + (errs.length ? errs.join('|') : 'none'));
              done();
            }, 3000);
          }, 350);
        }, 350);
      }, 350);
    })();
  }, 250);
})();
"""


def _run_probe(still):
    """Load the built page once, run every probe, return what it reported."""
    page = PAGE.read_text(encoding="utf-8").replace('data-theme=""', 'data-theme="light"')
    work = Path(tempfile.mkdtemp(prefix="jobhunt-probe-"))
    try:
        (work / "page.html").write_text(
            page.replace("</body>", f"<script>{PROBE}</script></body>"),
            encoding="utf-8")
        dump = work / "dom.html"
        command = [jh.find_browser(), "--headless=new", "--disable-gpu",
                   "--no-sandbox", "--no-first-run", "--disable-extensions",
                   "--disable-background-networking", "--disable-component-update",
                   "--window-size=1280,1057", f"--user-data-dir={work / 'p'}",
                   "--virtual-time-budget=20000", "--dump-dom"]
        # Both directions are forced. A CI runner reports reduced motion by
        # default, which silently turned the "moving" run into a second still
        # one - so the rail test was asserting movement against a page built
        # not to move.
        command.append("--force-prefers-reduced-motion" if still
                       else "--force-prefers-no-reduced-motion")
        command.append((work / "page.html").as_uri())

        with dump.open("wb") as sink:
            process = subprocess.Popen(command, stdout=sink, stderr=subprocess.DEVNULL)
        raw = jh._await_file(dump, process, 120, ready=jh._dom_complete)
        jh._stop(process)
        if raw is None:
            pytest.skip("the browser produced no DOM within 120s")
        body = raw.decode("utf-8", "replace")
        start = body.find('<pre id="measured"')
        if start < 0:
            pytest.fail("the probe never reported - the page script may have thrown")
        text = body[body.index(">", start) + 1:body.index("</pre>", start)]
        return dict(line.split("=", 1) for line in text.strip().splitlines()
                    if "=" in line)
    finally:
        shutil.rmtree(work, ignore_errors=True)


@pytest.fixture(scope="module")
def moving():
    """The page as most people see it."""
    if jh.find_browser() is None:
        pytest.skip("no Chromium-family browser")
    got = _run_probe(still=False)
    assert got["reduced"] == "false", (
        "the browser still reports reduced motion - --force-prefers-no-reduced-"
        "motion may have been dropped, and these tests would quietly measure "
        "the wrong page")
    return got


@pytest.fixture(scope="module")
def stilled():
    """The page for somebody who asked their machine for less movement."""
    if jh.find_browser() is None:
        pytest.skip("no Chromium-family browser")
    got = _run_probe(still=True)
    assert got["reduced"] == "true", "--force-prefers-reduced-motion did not take"
    return got


def pair(value):
    fill, lit = value.split(",")
    return float(fill), int(lit)


# --- what every reader must get ---------------------------------------------

def test_the_page_throws_nothing(moving):
    """One uncaught error and the arrivals never fire, which means a page with
    invisible sections rather than a visible bug."""
    assert moving["errors"] == "none", moving["errors"]


@pytest.mark.parametrize("part", ["hero-h1", "hero-cta", "hero-eyebrow",
                                  "hero-slider"])
def test_the_first_screenful_is_visible_at_rest(moving, part):
    """`.up` starts at opacity 0 and is revealed by an observer. If that never
    fires the page is blank, which looks like a broken site rather than a
    broken script, so nobody reports it."""
    assert moving["js"] == "true"
    assert moving[part] == "1", f"{part} is invisible"


@needs_browser
def test_the_headline_retypes_itself(moving):
    """The swapped half is the page's one moving headline. Checked by sampling
    it twice: the first sample is only the text the script seeds before the
    loop starts, and a broken animation passes that test happily - which it
    did, until this one sampled again later."""
    assert int(moving["typed"]) > 0, "nothing was typed at all"
    assert moving["typedMoved"] == "true", (
        f"the headline never changed: {moving['typed']} -> {moving['typedLater']}")


@needs_browser
def test_reduced_motion_leaves_a_whole_phrase_not_a_stub(stilled):
    """Nothing types, so whatever is there has to be a finished sentence."""
    sys.path.insert(0, str(ROOT / "tools" / "site"))
    import data
    assert int(stilled["typed"]) == len(data.HEADLINE_SWAP[0]), stilled["typed"]
    assert stilled["typedMoved"] == "false", "it moved anyway"


def test_the_headline_never_leaves_a_hole_without_script(page):
    """No script, no typing - so the phrase has to be in the markup, visible.
    The `.ghost` copy carries it and is un-hidden by a `html:not(.js)` rule."""
    sys.path.insert(0, str(ROOT / "tools" / "site"))
    import data
    longest = max(data.HEADLINE_SWAP, key=len)
    assert f'<span class="ghost">{longest}</span>' in page
    assert "html:not(.js) .type .ghost { visibility: visible; }" in page
    assert "html:not(.js) .type .live, html:not(.js) .type .caret" in page


def test_the_two_cvs_are_right_without_any_script(page):
    """The comparison is the argument the whole page makes, so its figures live
    in the markup and each bar takes its width from an inline property.

    They used to be filled in by JavaScript on an observer callback. A score
    stuck at zero beside an empty bar does not read as a missing animation -
    it reads as the answer, and the wrong one.
    """
    sys.path.insert(0, str(ROOT / "tools" / "site"))
    import data

    want = []
    for cv in (data.GENERIC, data.TAILORED):
        _, hits, total = data.cv_lines(cv)
        want.append((str(hits), str(total)))
    assert re.findall(r"<b>(\d+)<small>/(\d+)</small></b>", page) == want

    fills = [int(n) for n in re.findall(r"--fill:(\d+)%", page)]
    assert fills == [round(100 * int(h) / int(t)) for h, t in want], fills
    assert "@keyframes grow" in page, "the bars have no animation of their own"


def test_the_tailored_cv_adds_nothing(page):
    """The page's whole claim is that tailoring reorders rather than invents.
    If the example broke that, the page would be arguing against itself - and
    it did: the tailored card once showed a line the other never had.
    """
    sys.path.insert(0, str(ROOT / "tools" / "site"))
    import data

    assert sorted(data.GENERIC["order"]) == sorted(data.TAILORED["order"]), \
        "the two cards are not the same lines"
    assert sorted(data.GENERIC["order"]) == list(range(len(data.POOL))), \
        "one of them drops a line from the pool"

    _, weak, total = data.cv_lines(data.GENERIC)
    _, strong, _ = data.cv_lines(data.TAILORED)
    assert strong > weak, "tailoring changed nothing"
    assert strong == total, "the tailored one still buries something"

    # and the page says as much, in words
    assert "same six lines" in page.lower() or "same" in data.COMPARE_NOTE.lower()


def test_the_rail_fills_as_you_scroll_the_steps(moving):
    """A relationship rather than exact numbers: the fill is a fraction of the
    viewport height, so the values differ between a laptop and a CI runner."""
    above, into, past = (pair(moving[k]) for k in
                         ("railAbove", "railInto", "railPast"))
    assert above[0] < into[0] < past[0], f"the rail does not fill: {moving}"
    assert above[1] <= into[1] < past[1], f"the badges do not light: {moving}"
    assert past == (100.0, 4), f"it never completes: {moving}"


def test_the_install_routes_are_readable_without_javascript(moving):
    """A page that needs JS to say how to install it fails the person on a
    locked-down machine - who is exactly the person downloading a zip.

    Checked by computing `display` rather than by looking for the rule: the
    blanket `[hidden] { display: none !important }` beat the override once
    already, and the CSS text looked perfectly correct.
    """
    assert moving["nojsShown"] == moving["panels"], "not every route is shown"
    assert moving["nojsNamed"] == moving["panels"], "the routes are not labelled"
    assert moving["nojsPlaceholder"] == "none", "the placeholder is still there"
    assert int(moving["commands"]) >= 8, moving["commands"]


# --- and for somebody who asked for less movement ---------------------------

def test_reduced_motion_still_shows_the_whole_page(stilled):
    """The thing that matters about reduced motion is not that nothing moves,
    but that nothing is missing."""
    assert stilled["reduced"] == "true", "the flag did not take"
    for part in ("hero-h1", "hero-cta", "hero-eyebrow", "hero-slider"):
        assert stilled[part] == "1", f"{part} is invisible"
    assert pair(stilled["railPast"])[1] == 4, "the steps never light"
