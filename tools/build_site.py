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
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "site"))
import data  # noqa: E402
import logo  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
SITE = Path(__file__).resolve().parent / "site"
REPO = data.REPO
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
#: Downloads come from the latest release, not from docs/: GitHub counts
#: every download of a release file, and nothing else here can be counted.
RELEASE = f"https://github.com/{REPO}/releases/latest/download"

#: The mark, as a data URI - one request fewer and nothing to 404.
FAVICON = logo.favicon()

#: The same mark as a file, for the README, which cannot use a data URI.
LOGO = urllib.parse.unquote(FAVICON.split(",", 1)[1]) + "\n"


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
            f"<p>Paste these at the prompt. You get all {HOW_MANY}, and updates with "
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
        f'href="{RELEASE}/jobhunt-all.zip" download>{icon("download-simple")}'
        f"All {HOW_MANY} skills</a></p></div>")

    warn = " warn" if agent["scope"] == "project" else ""
    lead = "<b>Per project, not per user.</b> " if agent["scope"] == "project" else ""
    out.append(f'<div class="note{warn}">{lead}{e(agent["note"])}</div>')
    return "".join(out)


#: Spelled out because both places it appears are prose. Counted rather than
#: typed: the closer said "eleven" for a while after the twelfth was added.
_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven",
          "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen"]
HOW_MANY = _WORDS[len(data.read_skills())]

#: Repeated rows say nothing new to a screen reader.
HIDDEN = ' aria-hidden="true"' 


def demo(stage):
    """The little live panel beside one step of the workflow.

    Every panel is written in its *finished* state. The script and the
    stylesheet run it backwards to the start and play it forward when the step
    lights up - so with no script, or with reduced motion, a visitor simply
    sees the result, never an empty box.
    """
    kind = stage["kind"]
    if kind == "link":
        facts = "".join(f'<span class="chip" style="--i:{i}">{e(f)}</span>'
                        for i, f in enumerate(stage["facts"]))
        asks = "".join(f'<span class="chip ask" style="--i:{i + 3}">{e(a)}</span>'
                       for i, a in enumerate(stage["asks"]))
        body = (f'<div class="url">{icon("link-simple")}'
                f'<span class="typed" data-text="{e(stage["url"])}">{e(stage["url"])}</span></div>'
                f'<div class="chips">{facts}</div>'
                f'<div class="label">It asks for</div><div class="chips">{asks}</div>')
    elif kind == "score":
        rows = "".join(
            f'<li class="{"hit" if ok else "gap"}" style="--i:{i}">'
            f'{icon("check" if ok else "warning-circle")}<span>{e(name)}</span>'
            f'<em>{"in your work" if ok else "a real gap"}</em></li>'
            for i, (name, ok) in enumerate(stage["checks"]))
        hits = sum(1 for _, ok in stage["checks"] if ok)
        total = len(stage["checks"])
        body = (f'<div class="score"><b>{hits}<small>/{total}</small></b>'
                f'<span>requirements backed by your own work</span></div>'
                f'<div class="meter-line" style="--fill:{round(100 * hits / total)}%"><i></i></div>'
                f'<ul class="checks">{rows}</ul>')
    elif kind == "rewrite":
        # Five lines as the one CV has them, and where tailoring puts them.
        shown = [3, 4, 5, 0, 1]
        after = sorted(shown, key=lambda i: (not data.POOL[i][1], i))
        rows = "".join(
            f'<li class="{"strong" if data.POOL[i][1] else ""}" '
            f'style="--from:{n};--to:{after.index(i)}">{e(data.POOL[i][0])}</li>'
            for n, i in enumerate(shown))
        body = (f'<ol class="lines" style="--rows:{len(shown)}">{rows}</ol>'
                '<div class="fold"><span>most readers stop about here</span></div>')
    elif kind == "people":
        rows = "".join(
            f'<li class="{"best" if best else ""}" style="--i:{i}">'
            f'<span class="face">{e(ini)}</span>'
            f'<span class="who"><b>{e(name)}</b><small>{e(role)}</small></span>'
            f'<span class="tag">{e(tag)}</span></li>'
            for i, (ini, name, role, tag, best) in enumerate(stage["people"]))
        body = (f'<ul class="people">{rows}</ul>'
                f'<div class="query">{icon("magnifying-glass")}'
                f'<code>{e(stage["search"])}</code></div>')
    elif kind == "email":
        body = (f'<div class="to">To <b>{e(stage["to"])}</b></div>'
                f'<p class="msg"><span class="typed" data-text="{e(stage["message"])}">'
                f'{e(stage["message"])}</span></p>')
    elif kind == "letter":
        bars = "".join(f'<i style="--i:{i};--w:{w}%"></i>'
                       for i, w in enumerate((42, 96, 88, 93, 70, 95, 84, 58)))
        files = "".join(f'<span class="file" style="--i:{i}">{icon("file-text")}{e(f)}</span>'
                        for i, f in enumerate(stage["files"]))
        body = f'<div class="paper">{bars}</div><div class="files">{files}</div>'
    else:
        raise ValueError(kind)
    extra = " demo-rewrite" if kind == "rewrite" else ""
    return f'<div class="demo glass{extra}" aria-hidden="true">{body}</div>'


def build():
    css = (SITE / "style.css").read_text(encoding="utf-8")
    js = (SITE / "app.js").read_text(encoding="utf-8")
    enhance = (SITE / "enhance.js").read_text(encoding="utf-8")

    # The ghost holds the sentence's full size from the first frame, so the
    # page below it does not jump as characters land.
    headline = (
        f'{e(data.HEADLINE_FIXED)}<span class="type" '
        f'data-type="{e(data.HEADLINE_TYPED)}">'
        f'<span class="ghost">{e(data.HEADLINE_TYPED)}</span>'
        f'<span class="live" aria-hidden="true"></span></span>')

    # Whole copies, each carrying the gap that follows it, so translating by
    # exactly one copy lands the next one where it stood. The old version was
    # two copies translated -50%: half a gap short every lap, a 7px snap, and
    # 1428px of chips left 492px of blank inside a 1920px bar.
    one = "".join(brand(key) for key in data.BOARDS)
    # Only the first row is read out; the rest are the same five names again.
    boards = "".join(
        f'<div class="row"{"" if i == 0 else HIDDEN}>{one}</div>'
        for i in range(data.BOARD_COPIES))

    cv_plain = cv_card(data.GENERIC, best=False)
    cv_best = cv_card(data.TAILORED, best=True)
    graph = network()

    soon = "".join(
        f'<article class="soon-card"><div class="badge">{icon(s["icon"])}</div>'
        f'<h3>{e(s["title"])}</h3><p>{e(s["body"])}</p></article>'
        for s in data.SOON)

    steps = "".join(
        f'<div class="step"><div class="badge">{icon(s["icon"])}</div>'
        f'<div class="say"><span class="n">STEP {i + 1}'
        f'<span class="skill">{e(s["skill"])}</span></span>'
        f'<h3>{e(s["title"])}</h3><p>{e(s["body"])}</p></div>{demo(s)}</div>'
        for i, s in enumerate(data.FLOW))
    also = "".join(f'<li><code>{e(name)}</code><span>{e(what)}</span></li>'
                   for name, what in data.ALSO)

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

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>jobhunt — job applications you can stand behind</title>
<meta name="description"
      content="{e(data.NET_TITLE)} {e(data.DAY_SUB)}">
<meta name="color-scheme" content="dark">
<meta property="og:title" content="jobhunt">
<meta property="og:description"
      content="{e(data.HEADLINE_FIXED + data.HEADLINE_TYPED)}">
<meta property="og:type" content="website">
<link rel="icon" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap">
<style>{css}</style>
<script>
  /* Before first paint, so the motion may hide what it is about to move. */
  document.documentElement.className += " js";
</script>
</head>
<body>

<header class="bar">
  <div class="wrap">
    <div class="pill glass">
      <a class="mark" href="#top">{logo.mark(26)}jobhunt</a>
      <nav>
        <a href="#how" class="hide-sm">How it works</a>
        <a href="#example" class="hide-sm">The difference</a>
        <a href="https://github.com/{REPO}" class="icon-sm" title="GitHub">
          {icon("github-logo")}<span class="label">GitHub</span></a>
        <a href="https://github.com/{REPO}" class="star icon-sm"
           title="Starring it helps people find it">{icon("star")}<span
           class="label">Star</span></a>
        <a href="#install">Install</a>
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
    <div class="track" style="--copies: {data.BOARD_COPIES}">{boards}</div>
  </div>
</div>

<section id="example">
  <div class="wrap">
    <div class="sec-head wide up">
      <span class="kicker">{icon("link-simple")}The same six lines, twice</span>
      <h2>{e(data.COMPARE_TITLE)}</h2>
      <p>{e(data.COMPARE_SUB)}</p>
    </div>
    <div class="versus up">
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
</section>

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
  </div>
</div>

<section id="how">
  <div class="wrap">
    <div class="sec-head wide up">
      <span class="kicker">{icon("cursor-click")}How it works</span>
      <h2>{e(data.FLOW_TITLE)}</h2>
      <p>{e(data.FLOW_SUB)}</p>
    </div>
    <div class="steps">
      <div class="rail"><i></i></div>
      {steps}
    </div>
    <div class="also up">
      <span class="label">Also in the kit</span>
      <ul>{also}</ul>
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
      <p>Pick one and copy the command. Every route gives you the same {HOW_MANY}
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
        same as all {HOW_MANY}.</p></details>
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
    <p>{HOW_MANY.capitalize()} skills, no account, nothing to install. It
       applies to nothing — that part stays yours.</p>
    <div class="cta">
      <a class="btn btn-go" href="#install">Install{icon("arrow-right")}</a>
      <a class="btn btn-ghost" href="https://github.com/{REPO}">Read the source</a>
    </div>
  </div>
</div>

</main>

<footer>
  <div class="wrap">
    <p>Free for your own job search, not for commercial use. It applies to
       nothing and sends nothing.</p>
    <nav>
      <a href="https://github.com/{REPO}">Source</a>
      <a href="https://github.com/{REPO}/blob/main/LICENSE">License</a>
      <a href="https://github.com/{REPO}/issues">Issues</a>
      <a href="{RELEASE}/jobhunt-all.zip" download>Download</a>
    </nav>
  </div>
</footer>

<script>{js}</script>
<script type="module">{enhance}</script>
</body>
</html>
"""
    return page


def main(argv):
    check = "--check" in argv
    page = build()
    made = {OUT / "index.html": page, OUT / "assets" / "logo.svg": LOGO}

    if check:
        for target, body in made.items():
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            if current != body:
                print(f"{target.relative_to(ROOT)} is out of date.\n\n"
                      "Run: python tools/build_site.py", file=sys.stderr)
                return 1
        print(f"checked docs/index.html ({len(page) // 1024} KB) and the logo")
        return 0

    for target, body in made.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote docs/index.html ({len(page) // 1024} KB) and docs/assets/logo.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
