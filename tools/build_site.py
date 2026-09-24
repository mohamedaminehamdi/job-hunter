#!/usr/bin/env python3
"""Build docs/index.html - one page, for someone looking for a job.

Generated from the skills themselves, so it cannot advertise one that does not
exist or describe one that has changed. The build fails if a skill is added
without being listed in tools/site/data.py.

    python tools/build_site.py
    python tools/build_site.py --check    exit 1 if docs/ is stale
"""

import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "site"))
import data  # noqa: E402
import logo  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
SITE = Path(__file__).resolve().parent / "site"
REPO = data.REPO
RAW = f"https://raw.githubusercontent.com/{REPO}/main"

#: A dot in the accent, as a data URI - one request fewer and nothing to 404.
FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' "
           "viewBox='0 0 16 16'><circle cx='8' cy='8' r='7' fill='%2312664a'/>"
           "</svg>")


def e(value):
    return html.escape(str(value), quote=True)


def icon(name, extra=""):
    """A Phosphor glyph, inlined. Drawn by them, not by me."""
    klass = f"ico {extra}".strip()
    return (f'<svg class="{klass}" viewBox="0 0 256 256" aria-hidden="true">'
            f"{data.ICONS[name]}</svg>")


def brand(key):
    mark = data.BRANDS[key]
    return (f'<span class="board glass"><svg viewBox="0 0 24 24" aria-hidden="true">'
            f'<path d="{mark["path"]}"/></svg>'
            f'<span>{e(mark["title"])}</span></span>')


def command(text, label="command"):
    return (f'<div class="cmd"><code>{e(text)}</code>'
            f'<button class="copy" type="button" data-copy="{e(text)}" '
            f'aria-label="Copy {e(label)}">{icon("copy", "i-copy")}'
            f'{icon("check", "i-done")}<span>Copy</span></button></div>')


def cv_card(cv, best):
    """One of the two CVs. Same component, and one of them held back."""
    lines, hits, total = data.cv_lines(cv)
    rows = "".join(f'<li class="{"hit" if hit else ""}">{e(text)}</li>'
                   for text, hit in lines)
    tag = "Tailored" if best else "Generic"
    return (
        f'<article class="cv {"best" if best else "plain"}">'
        f'<div class="cv-top">{icon("file-text")}<span>{e(cv["label"])}</span>'
        f'<span class="tag">{tag}</span></div>'
        f'<div class="cv-body"><p class="cv-summary">{e(cv["summary"])}</p>'
        f'<ul class="cv-lines">{rows}</ul></div>'
        f'<div class="cv-foot"><div class="cv-score">'
        f"<b>{hits}<small>/{total}</small></b>"
        f"<span>of what this job asks for, in the first screenful</span></div>"
        f'<div class="cv-bar" style="--fill:{round(100 * hits / total)}%"><i></i></div>'
        f'<p class="cv-note">{e(cv["note"])}</p></div></article>')


def network():
    """You, three people, the job - and the edge that actually gets answered.

    Hand-drawn SVG rather than a diagram library: it is five circles and four
    curves, and the whole page is meant to be one file with nothing to fetch.
    """
    people = data.NET_PEOPLE
    # Tall enough that a node's caption clears the next node's circle: rows
    # are height/(n+1) apart, the caption sits 42 below its centre, and the
    # circle is 24 in radius.
    width, height = 540, 350
    left, right = 46, width - 46
    middle = width / 2
    rows = [height * (i + 1) / (len(people) + 1) for i in range(len(people))]
    centre = height / 2

    def curve(x1, y1, x2, y2):
        """A flat S between two points, so edges never overlap the labels."""
        bend = (x2 - x1) * 0.45
        return f"M{x1},{y1} C{x1 + bend},{y1} {x2 - bend},{y2} {x2},{y2}"

    edges, nodes, sparks = [], [], []
    for person, y in zip(people, rows):
        best = " best" if person["best"] else ""
        into = curve(left + 30, centre, middle - 30, y)
        out = curve(middle + 30, y, right - 34, centre)
        edges.append(f'<path class="edge{best}" d="{into}"/>'
                     f'<path class="edge{best}" d="{out}"/>')
        if person["best"]:
            # One pulse, along the one edge worth drawing attention to.
            sparks.append(f'<path class="spark" d="{into}"/>'
                          f'<path class="spark" d="{out}"/>')
        nodes.append(
            f'<g class="node{best}"><circle cx="{middle}" cy="{y}" r="24"/>'
            f'<text x="{middle}" y="{y + 4}">{e(person["who"])}</text>'
            f'<text class="sub" x="{middle}" y="{y + 42}">'
            f'{e(person["role"])}</text></g>')

    nodes.append(f'<g class="node you"><circle cx="{left}" cy="{centre}" r="26"/>'
                 f'<text x="{left}" y="{centre + 4}">You</text></g>')
    nodes.append(f'<g class="node job"><circle cx="{right}" cy="{centre}" r="30"/>'
                 f'<text x="{right}" y="{centre + 4}">Job</text></g>')

    return (f'<svg viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="You, three people at the company, and the job">'
            + "".join(edges) + "".join(sparks) + "".join(nodes) + "</svg>")


def routes(agent):
    """Every way of installing, for one agent, easiest first."""
    out, n = [], 0

    if agent["plugin"]:
        n += 1
        out.append(
            f'<div class="route"><h3><span class="num">{n}</span>'
            f'Inside {e(agent["name"])}<span class="best">easiest</span></h3>'
            "<p>Paste these at the prompt. You get all eleven, and updates with "
            "one command.</p>"
            + command(f"/plugin marketplace add {REPO}", "marketplace command")
            + command("/plugin install jobhunt@jobhunt", "install command")
            + "</div>")

    n += 1
    if agent["scope"] == "project":
        shell = f'sh -s -- --to {agent["path"].split("/")[0]}'
        where = " Run it in the folder you want to use for your job search."
        best = '<span class="best">easiest</span>'
    else:
        # No --to: install.sh finds what is there, and says so plainly when it
        # finds nothing.
        shell, where = "sh", ""
        best = "" if agent["plugin"] else '<span class="best">easiest</span>'
    out.append(
        f'<div class="route"><h3><span class="num">{n}</span>'
        f"One line in your terminal{best}</h3>"
        f"<p>macOS and Linux. It finds your agent and copies the skills in.{where}</p>"
        + command(f"curl -fsSL {RAW}/install.sh | {shell}", "install command")
        + "</div>")

    n += 1
    place = (f"<code>{e(agent['path'])}</code>" if agent["path"]
             else "wherever your agent reads skills from")
    out.append(
        f'<div class="route"><h3><span class="num">{n}</span>Download a folder</h3>'
        f"<p>No terminal at all. Unzip it and put the folder in {place} — make "
        "that directory if it is not there yet.</p>"
        f'<p style="margin-top:14px"><a class="btn btn-ghost" '
        f'href="download/jobhunt-all.zip" download>{icon("download-simple")}'
        "All eleven skills</a></p></div>")

    warn = " warn" if agent["scope"] == "project" else ""
    lead = "<b>Per project, not per user.</b> " if agent["scope"] == "project" else ""
    out.append(f'<div class="note{warn}">{lead}{e(agent["note"])}</div>')
    return "".join(out)


def build():
    skills = data.read_skills()
    css = (SITE / "style.css").read_text(encoding="utf-8")
    js = (SITE / "app.js").read_text(encoding="utf-8")

    # The swapped half is sized by the longest option so nothing below it
    # jumps as characters land.
    longest = max(data.HEADLINE_SWAP, key=len)
    headline = (
        f'{e(data.HEADLINE_FIXED)}<span class="type" '
        f'data-swap="{e("|".join(data.HEADLINE_SWAP))}">'
        f'<span class="ghost">{e(longest)}</span>'
        f'<span class="live" aria-hidden="true"></span>'
        f'<i class="caret" aria-hidden="true"></i></span> '
        f"{e(data.HEADLINE_TAIL)}")

    # Doubled, so the track can translate half its width and start over with
    # no visible seam.
    one = "".join(brand(key) for key in data.BOARDS)
    boards = one + one

    cv_plain = cv_card(data.GENERIC, best=False)
    cv_best = cv_card(data.TAILORED, best=True)
    graph = network()

    soon = "".join(
        f'<article class="soon-card"><div class="badge">{icon(s["icon"])}</div>'
        f'<h3>{e(s["title"])}</h3><p>{e(s["body"])}</p></article>'
        for s in data.SOON)

    steps = "".join(
        f'<div class="step"><div class="badge">{icon(s["icon"])}</div>'
        f'<div><span class="n">STEP {i + 1}</span><h3>{e(s["title"])}</h3>'
        f'<p>{e(s["body"])}</p></div></div>'
        for i, s in enumerate(data.STEPS))

    agent_buttons = []
    for group, label in (("global", "Installs everywhere"),
                         ("project", "Per project"), ("manual", "Anything else")):
        members = [a for a in data.AGENTS if a["scope"] == group]
        if not members:
            continue
        agent_buttons.append(f'<div class="group">{e(label)}</div>')
        for agent in members:
            agent_buttons.append(
                f'<button type="button" role="tab" data-agent="{e(agent["id"])}" '
                f'aria-selected="false">{icon("check", "tick")}'
                f'<span>{e(agent["name"])}</span></button>')

    panels = "".join(
        f'<div class="agent-panel" data-for="{e(a["id"])}" hidden>'
        f'<div class="panel-name">{e(a["name"])}</div>{routes(a)}</div>'
        for a in data.AGENTS)

    cards = []
    for skill in skills:
        wide = " wide" if skill["name"] == "jobhunt" else ""
        cards.append(
            f'<a class="skill{wide}" href="download/{e(skill["name"])}.zip" '
            f'download><div class="badge">{icon(skill["icon"])}</div>'
            f'<div class="say"><h3>{e(skill["headline"])}</h3>'
            f'<p>{e(skill["plain"])}</p>'
            f'<span class="id">{e(skill["name"])}</span></div></a>')

    page = f"""<!doctype html>
<html lang="en" data-theme="">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>jobhunt — job applications you can stand behind</title>
<meta name="description"
      content="{e(data.NET_TITLE)} {e(data.DAY_SUB)}">
<meta name="color-scheme" content="light dark">
<meta property="og:title" content="jobhunt">
<meta property="og:description"
      content="{e(data.HEADLINE_FIXED + data.HEADLINE_SWAP[0])} {e(data.HEADLINE_TAIL)}">
<meta property="og:type" content="website">
<link rel="icon" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap">
<style>{css}</style>
<script>
  /* Before first paint: marks that script runs, so the motion may hide things,
     and applies a saved theme so the page does not flash the wrong one. */
  (function () {{
    var r = document.documentElement;
    r.className += " js";
    try {{
      var t = localStorage.getItem("jobhunt-theme");
      if (t === "light" || t === "dark") r.setAttribute("data-theme", t);
    }} catch (e) {{}}
  }})();
</script>
</head>
<body>

<header class="bar">
  <div class="wrap">
    <div class="pill glass">
      <a class="mark" href="#top">{logo.mark(26)}jobhunt</a>
      <nav>
        <a href="#how" class="hide-sm">How it works</a>
        <a href="#skills" class="hide-sm">Skills</a>
        <a href="https://github.com/{REPO}" class="hide-sm">
          {icon("github-logo")}GitHub</a>
        <a href="https://github.com/{REPO}" class="star hide-sm"
           title="Starring it helps people find it">{icon("star")}Star</a>
        <a href="#install">Install</a>
        <button class="tog" type="button" id="theme" aria-label="Switch theme">
          {icon("sun", "i-sun")}{icon("moon", "i-moon")}
        </button>
      </nav>
    </div>
  </div>
</header>

<main id="top">

<div class="field">
  <div class="wrap hero">
    <span class="eyebrow glass up">{icon("briefcase")}Works with any job link</span>
    <h1 class="up">{headline}</h1>
    <div class="cta up">
      <a class="btn btn-go" href="#install">Install{icon("arrow-right")}</a>
      <a class="btn btn-ghost" href="#how">See how it works</a>
    </div>
  </div>

  <div class="slider up" aria-label="Works with postings from these boards">
    <div class="track">{boards}</div>
  </div>

  <div class="wrap">
  <div class="wrap versus up">
    <div class="versus-head">
      <span class="for glass">{icon("link-simple")}{e(data.JOB)}</span>
    </div>
    <div class="pair">
      {cv_plain}
      {cv_best}
    </div>
    <p class="versus-foot">{e(data.COMPARE_NOTE)}</p>
  </div>
</div>

<div class="night" id="cost">
  <div class="wrap">
    <div class="sec-head wide up">
      <span class="kicker">{icon("clock-countdown")}What it takes off your plate</span>
      <h2>{e(data.DAY_TITLE)}</h2>
      <p>{e(data.DAY_SUB)}</p>
    </div>
    <div class="race up" data-tasks="{e(chr(124).join(data.DAY_TASKS))}">
      <div class="lane slow">
        <div class="lane-top"><b>{e(data.DAY_BY_HAND["label"])}</b>
          <span class="unit">{data.DAY_BY_HAND["count"]} {e(data.DAY_BY_HAND["unit"])}</span>
          <span class="clock">{e(data.DAY_BY_HAND["time"])}</span></div>
        <div class="meter"><i></i></div>
        <div class="lane-foot"><span class="doing">{e(data.DAY_TASKS[0])}</span></div>
      </div>
      <div class="lane fast">
        <div class="lane-top"><b>{e(data.DAY_WITH["label"])}</b>
          <span class="unit">{data.DAY_WITH["count"]} {e(data.DAY_WITH["unit"])}</span>
          <span class="clock">{e(data.DAY_WITH["time"])}</span></div>
        <div class="meter"><i></i></div>
        <div class="lane-foot">{e(data.DAY_WITH["note"])}</div>
      </div>
    </div>

    <div class="wont up">
      <div class="badge">{icon("shield-check")}</div>
      <div>
        <h3>It still won't write you a career you don't have</h3>
        <p>Every line comes out of your own profile, and anything it can't
           trace back is flagged before you send it. Faster, not looser.</p>
        <span class="said"><em>{e(data.FLAG["claim"])}</em>{e(data.FLAG["finding"])}</span>
      </div>
    </div>
  </div>
</div>

<section id="how">
  <div class="wrap">
    <div class="sec-head wide up">
      <span class="kicker">{icon("cursor-click")}How it works</span>
      <h2>You bring the link. It brings the evidence.</h2>
    </div>
    <div class="steps">
      <div class="rail"><i></i></div>
      {steps}
    </div>
  </div>
</section>

<div class="band" id="outreach">
  <div class="wrap">
    <div class="sec-head wide up">
      <span class="kicker">{icon("magnifying-glass")}Who to message</span>
      <h2>{e(data.NET_TITLE)}</h2>
      <p>{e(data.NET_SUB)}</p>
    </div>
    <div class="net">
      <div class="graph up">{graph}</div>
      <div class="draft glass up">
        <h4>{icon("paper-plane-tilt")}Drafted for you</h4>
        <blockquote>{e(data.OUTREACH_MESSAGE)}</blockquote>
        <p class="meta">{e(data.OUTREACH_NOTE)}</p>
      </div>
    </div>
  </div>
</div>

<div class="night" id="soon">
  <div class="wrap">
    <div class="sec-head wide up">
      <span class="kicker">{icon("clock-countdown")}Coming soon</span>
      <h2>{e(data.SOON_TITLE)}</h2>
    </div>
    <div class="soon stagger">{soon}</div>
    <p class="soon-note up">{icon("clock-countdown")}
      <span>{e(data.SOON_NOTE)}</span></p>
  </div>
</div>

<section id="install">
  <div class="wrap">
    <div class="sec-head wide up">
      <span class="kicker">{icon("download-simple")}Install</span>
      <h2>Which agent do you use?</h2>
      <p>Pick one and copy the command. Every route gives you the same eleven
         skills — there is no paid tier and nothing to sign up for.</p>
    </div>
    <div class="picker up">
      <div class="agents" role="tablist" aria-label="Choose your coding agent">
        {"".join(agent_buttons)}
      </div>
      <div class="panel" id="panel">
        <div class="panel-empty" id="panel-empty">
          {icon("cursor-click")}<p>Choose your agent on the left.</p>
        </div>
        {panels}
      </div>
    </div>
  </div>
</section>

<section id="skills">
  <div class="wrap">
    <div class="sec-head wide up">
      <span class="kicker">{icon("briefcase")}What gets installed</span>
      <h2>Eleven skills.</h2>
      <p>Each works on its own, or all of them together.</p>
    </div>
    <div class="grid stagger">{"".join(cards)}</div>
  </div>
</section>

<section id="faq">
  <div class="wrap">
    <div class="sec-head up">
      <span class="kicker">{icon("warning-circle")}Questions</span>
      <h2>The ones worth asking first.</h2>
    </div>
    <div class="faq up">
      <details><summary>Does it apply to jobs for me?</summary>
        <p>Not yet — that is on the way, for the boards that allow it. Today it
        prepares the application and hands it to you.</p></details>
      <details><summary>Do I need to pay for anything?</summary>
        <p>No. Your coding agent is the model, so whatever you already pay for
        covers it. There is no provider to sign up to and no token bill.</p>
        </details>
      <details><summary>Can I just use one skill?</summary>
        <p>Yes. Each folder carries its own copy of the library and imports
        nothing from its siblings, so one installed alone works exactly the
        same as all eleven.</p></details>
      <details><summary>Will it make my CV good?</summary>
        <p>It will make your CV <b>accurate</b>, and put your strongest
        evidence where a reader meets it. It cannot give you experience you do
        not have, and it will tell you plainly when a job needs some.</p>
        </details>
    </div>
  </div>
</section>

<div class="closer">
  <div class="wrap up">
    <h2>Your next application, in one command.</h2>
    <p>Eleven skills, no account, nothing to install. It applies to nothing —
       that part stays yours.</p>
    <div class="cta">
      <a class="btn btn-go" href="#install">Install{icon("arrow-right")}</a>
      <a class="btn btn-ghost" href="https://github.com/{REPO}">Read the source</a>
    </div>
  </div>
</div>

</main>

<footer>
  <div class="wrap">
    <p>MIT licensed. It applies to nothing and sends nothing.</p>
    <nav>
      <a href="https://github.com/{REPO}">Source</a>
      <a href="https://github.com/{REPO}/issues">Issues</a>
      <a href="download/jobhunt-all.zip" download>Download</a>
    </nav>
  </div>
</footer>

<script>{js}</script>
</body>
</html>
"""
    return page


def main(argv):
    check = "--check" in argv
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "index.html"
    page = build()

    if check:
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current != page:
            print("docs/index.html is out of date.\n\nRun: python tools/build_site.py",
                  file=sys.stderr)
            return 1
        print(f"checked docs/index.html ({len(page) // 1024} KB)")
        return 0

    target.write_text(page, encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote docs/index.html ({len(page) // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
