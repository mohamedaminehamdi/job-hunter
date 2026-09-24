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
    fit = data.FIT

    headline = "".join(f"<span>{e(line)}</span>" for line in data.HEADLINE)

    boards = "".join(brand(key) for key in data.BOARDS)
    boards += '<span class="board-more">…or any job URL</span>'

    three = "".join(
        f'<article class="card"><div class="badge">{icon(r["icon"])}</div>'
        f'<h3>{e(r["title"])}</h3><p>{e(r["body"])}</p></article>'
        for r in data.REASONS)

    steps = "".join(
        f'<div class="step"><div class="badge">{icon(s["icon"])}</div>'
        f'<div><span class="n">STEP {i + 1}</span><h3>{e(s["title"])}</h3>'
        f'<p>{e(s["body"])}</p></div></div>'
        for i, s in enumerate(data.STEPS))

    findings = "".join(
        f'<p class="finding">{icon("warning-circle")}<span>{e(f)}</span></p>'
        for f in data.FLAG["findings"])

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
<meta name="description" content="{e(data.SUB)}">
<meta name="color-scheme" content="light dark">
<meta property="og:title" content="jobhunt">
<meta property="og:description" content="{e(' '.join(data.HEADLINE))}">
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
      <a class="mark" href="#top"><span class="dot"></span>jobhunt</a>
      <nav>
        <a href="#how" class="hide-sm">How it works</a>
        <a href="#skills" class="hide-sm">Skills</a>
        <a href="https://github.com/{REPO}" class="hide-sm">GitHub</a>
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
    <p class="lede up">{e(data.SUB)}</p>
    <div class="cta up">
      <a class="btn btn-go" href="#install">Install{icon("arrow-right")}</a>
      <a class="btn btn-ghost" href="#how">See how it works</a>
    </div>
    <p class="cta-note up">Free. No API key. Nothing to install.</p>

    <div class="boards up">
      <p>Paste a link from</p>
      <div class="board-row stagger">{boards}</div>
    </div>
  </div>

  <div class="wrap proof-out">
    <div class="proof up">
    <div class="proof-head">{icon("folder-simple")}
      2026-09-24-acme-senior-data-engineer</div>
    <div class="proof-body">
      <div>
        <h3>What it caught</h3>
        <p class="claim">{e(data.FLAG["claim"])}</p>
        {findings}
      </div>
      <div>
        <h3>How you actually match</h3>
        <div class="score">
          <div>
            <div class="score-row">
              <span class="score-label">Backed by your CV</span>
              <span class="score-num"
                data-count="{fit['evidenced']}">{fit['evidenced']}<small>/{fit['of']}</small></span>
            </div>
            <div class="score-bar flat"
                 style="--fill:{round(100 * fit['evidenced'] / fit['of'])}%"><i></i></div>
            <p class="score-note">A fact about you. Tailoring cannot move it.</p>
          </div>
          <div>
            <div class="score-row">
              <span class="score-label">Seen in the first screenful</span>
              <span class="score-num"
                data-count="{fit['after']}">{fit['after']}<small>/{fit['backed']}</small></span>
              <span class="score-move">+{fit['after'] - fit['before']}</span>
            </div>
            <div class="score-bar"
                 style="--fill:{round(100 * fit['after'] / fit['backed'])}%"><i></i></div>
            <p class="score-note">This is the one tailoring is for.</p>
          </div>
        </div>
        </div>
      </div>
    </div>
  </div>
</div>

<section id="why">
  <div class="wrap">
    <div class="sec-head up">
      <span class="kicker">{icon("shield-check")}Why this one</span>
      <h2>Every CV tool will write you a better career.</h2>
      <p>This one can't. Three decisions do most of that work.</p>
    </div>
    <div class="three stagger">{three}</div>
  </div>
</section>

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
      <span class="kicker">{icon("briefcase")}Eleven skills</span>
      <h2>Take all of them, or take one.</h2>
      <p>Each works on its own. Install just the checker to look over a letter
         you wrote yourself, or just the score to decide whether a job is worth
         an evening.</p>
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
        <p>No, and it won't be made to. It makes the documents; you send them.
        Some employers disqualify applications the applicant didn't write, and
        that's their call to make.</p></details>
      <details><summary>Do I need to pay for anything?</summary>
        <p>No. Your coding agent is the model, so whatever you already pay for
        covers it. There's no provider to sign up to, no token bill, and nothing
        is uploaded anywhere.</p></details>
      <details><summary>Does it scrape LinkedIn?</summary>
        <p>No. LinkedIn walls and throttles automated access and the risk of
        working around that would land on your account. It works out who's worth
        messaging and builds the search — you run it and press send.</p></details>
      <details><summary>What do I need installed?</summary>
        <p>Python 3.9 or newer, which macOS and every Linux already has, and
        Chrome, Chromium, Edge or Brave for reading job pages and making PDFs.
        Without a browser you still get markdown.</p></details>
      <details><summary>Where does my CV go?</summary>
        <p>Into a <code>jobhunt/</code> folder in whatever directory you work in,
        and nowhere else. It never leaves your machine.</p></details>
      <details><summary>Will it make my CV good?</summary>
        <p>It will make your CV <b>accurate</b>, and put your strongest evidence
        where a reader meets it. It can't give you experience you don't have, and
        it will tell you plainly when a job needs some.</p></details>
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
