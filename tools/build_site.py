#!/usr/bin/env python3
"""Build docs/index.html - the page someone lands on before installing anything.

Generated rather than hand-written so it cannot advertise a skill that does not
exist or describe one that has changed: every card is read from that skill's own
SKILL.md, and the build fails if a skill is added without being listed.

    python tools/build_site.py
    python tools/build_site.py --check    exit 1 if docs/ is stale
"""

import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "site"))
import data  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
SITE = Path(__file__).resolve().parent / "site"
REPO = data.REPO
RAW = f"https://raw.githubusercontent.com/{REPO}/main"


def e(value):
    return html.escape(str(value), quote=True)


ICONS = {
    "tick": '<path d="M2.5 8.2l3.6 3.6L13.5 4.4" fill="none" stroke="currentColor" '
            'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>',
    "copy": '<rect x="5.5" y="5.5" width="8" height="8" rx="1.6" fill="none" '
            'stroke="currentColor" stroke-width="1.5"/><path d="M10.5 3.5h-6a1 1 0 '
            '00-1 1v6" fill="none" stroke="currentColor" stroke-width="1.5" '
            'stroke-linecap="round"/>',
    "down": '<path d="M8 2.5v8m0 0L4.8 7.3M8 10.5l3.2-3.2M2.5 13.5h11" fill="none" '
            'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" '
            'stroke-linejoin="round"/>',
    "sun":  '<circle cx="8" cy="8" r="3.2" fill="none" stroke="currentColor" '
            'stroke-width="1.5"/><path d="M8 1v1.6M8 13.4V15M15 8h-1.6M2.6 8H1'
            'M12.9 3.1l-1.1 1.1M4.2 11.8l-1.1 1.1M12.9 12.9l-1.1-1.1M4.2 4.2L3.1 3.1" '
            'stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
    "moon": '<path d="M13.2 9.6A5.7 5.7 0 016.4 2.8a5.8 5.8 0 106.8 6.8z" '
            'fill="none" stroke="currentColor" stroke-width="1.5" '
            'stroke-linejoin="round"/>',
    "point": '<path d="M8 1.8l5.6 3.2v6L8 14.2 2.4 11V5z" fill="none" '
             'stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>',
}


def icon(name, cls=""):
    klass = f' class="{cls}"' if cls else ""
    return (f'<svg{klass} viewBox="0 0 16 16" aria-hidden="true">{ICONS[name]}</svg>')


def colour(block):
    """Mark up a captured terminal block: figures, findings, headings."""
    out = e(block)
    out = re.sub(r"^(\$ .+)$", r"<b>\1</b>", out, flags=re.M)
    out = re.sub(r"(\+\d+)", r'<span class="ok">\1</span>', out)
    out = re.sub(r"^(\s*·.*)$", r'<span class="no">\1</span>', out, flags=re.M)
    out = re.sub(r"^(The figure .+|&#x27;.+?&#x27; (?:does not|is the) .+)$",
                 r'<span class="no">\1</span>', out, flags=re.M)
    out = re.sub(r"(\(unchanged by tailoring[^)]*\)|\(judge these yourself\))",
                 r'<span class="fade">\1</span>', out)
    return out


def terminal(label, block):
    return (f'<div class="term"><div class="term-head"><i></i><i></i><i></i>'
            f"<b>{e(label)}</b></div><pre>{colour(block)}</pre></div>")


def command_block(text, label="command"):
    return (f'<div class="cmd"><code>{e(text)}</code>'
            f'<button class="copy" data-copy="{e(text)}" type="button" '
            f'aria-label="Copy {e(label)}">'
            f'{icon("copy", "i-copy")}{icon("tick", "i-copied")}'
            f"<span>Copy</span></button></div>")


def routes_for(agent, skills):
    """Every way of installing, for one agent, best first."""
    out = []
    n = 0

    if agent["plugin"]:
        n += 1
        out.append(
            f'<div class="route"><h3><span class="num">{n}</span>'
            f'From inside {e(agent["name"])}<span class="best">easiest</span></h3>'
            "<p>Paste this at the prompt. It installs all eleven and keeps them "
            "up to date.</p>"
            + command_block(f"/plugin marketplace add {REPO}", "plugin command")
            + command_block("/plugin install jobhunt@jobhunt", "install command")
            + "</div>")

    n += 1
    # `sh -s -- <args>` is only needed when there are arguments to pass. A bare
    # trailing `--` reads as a command that got cut off.
    if agent["scope"] != "project":
        # Global, or an agent we do not know: no --to, because install.sh finds
        # what is there on its own and says so plainly when it finds nothing.
        shell, scope = "sh", ""
        best = "" if agent["plugin"] else "<span class='best'>easiest</span>"
    else:
        shell = f'sh -s -- --to {agent["path"].split("/")[0]}'
        scope = " Run it in the folder you want to use for your job search."
        best = "<span class='best'>easiest</span>"
    out.append(
        f'<div class="route"><h3><span class="num">{n}</span>One command in your '
        f"terminal{best}</h3>"
        f"<p>Works on macOS and Linux. It finds your agent and copies the "
        f"skills in.{scope}</p>"
        + command_block(f"curl -fsSL {RAW}/install.sh | {shell}", "install command")
        + "</div>")

    n += 1
    where = e(agent["path"]) if agent["path"] else "wherever your agent reads skills from"
    out.append(
        f'<div class="route"><h3><span class="num">{n}</span>Download a folder'
        "</h3><p>No terminal. Unzip it and put the folder in "
        f"<code>{where}</code> — make that directory if it is not there yet.</p>"
        f'<p style="margin-top:12px"><a class="btn btn-ghost" '
        f'href="download/jobhunt-all.zip" download>{icon("down")}'
        "All eleven skills</a></p></div>")

    if agent["note"]:
        # The warning colour is for the thing people get wrong - skills that
        # live in the project rather than in your home directory. Everything
        # else is just information and is styled as such.
        cls = "scope-note warn" if agent["scope"] == "project" else "scope-note"
        label = "Per project, not per user. " if agent["scope"] == "project" else ""
        out.append(f'<div class="{cls}">'
                   + (f"<b>{label}</b>" if label else "")
                   + f'{e(agent["note"])}</div>')

    return "".join(out)


#: A dot in the accent, as a data URI - one request fewer and nothing to 404.
FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' "
           "viewBox='0 0 16 16'><circle cx='8' cy='8' r='7' fill='%2314664a'/>"
           "</svg>")


def build():
    skills = data.read_skills()
    favicon = FAVICON
    css = (SITE / "style.css").read_text(encoding="utf-8")
    js = (SITE / "app.js").read_text(encoding="utf-8")

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
                f'aria-selected="false">{icon("tick", "tick")}'
                f'<span>{e(agent["name"])}</span></button>')

    # Every panel carries its agent's name, shown only when the script has not
    # run. Without JS all the panels are displayed at once, and an unlabelled
    # stack of install routes is useless.
    panels = "".join(
        f'<div class="agent-panel" data-for="{e(a["id"])}" hidden>'
        f'<div class="panel-name">{e(a["name"])}</div>'
        f"{routes_for(a, skills)}</div>" for a in data.AGENTS)

    cards = []
    for skill in skills:
        wide = ' wide' if skill["name"] == "jobhunt" else ""
        runs = ('<span class="runs">runs the rest</span>' if skill["name"] == "jobhunt"
                else "")
        cards.append(
            f'<article class="skill{wide} rise">'
            f'<div class="skill-top"><h3>{e(skill["headline"])}</h3>'
            f'<span class="id">{e(skill["name"])}</span>{runs}</div>'
            f'<p>{e(skill["plain"])}</p>'
            f'<a class="get" href="download/{e(skill["name"])}.zip" download>'
            f'{icon("down")}Download this one</a></article>')

    files = "".join(
        f'<li><code>{e(name)}</code><span>{e(what)}</span></li>'
        for name, what in data.RUN_FILES)

    reasons = "".join(
        f"<div><h3>{e(r['title'])}</h3><p>{r['body']}</p></div>" for r in data.REASONS)

    page = f"""<!doctype html>
<html lang="en" data-theme="">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>jobhunt — job application skills for your coding agent</title>
<meta name="description" content="{e(data.SUB)}">
<meta name="color-scheme" content="light dark">
<meta property="og:title" content="jobhunt">
<meta property="og:description" content="{e(data.HEADLINE)}">
<meta property="og:type" content="website">
<link rel="icon" href="{favicon}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap">
<style>{css}</style>
<script>
  /* Before first paint: marks that script runs, so the entrance animation may
     hide things, and applies a saved theme so the page does not flash. */
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
    <a class="mark" href="#top"><span class="dot"></span>jobhunt</a>
    <nav>
      <a href="#install">Install</a>
      <a href="#skills">Skills</a>
      <a href="#how" class="hide-sm">How it works</a>
      <a href="https://github.com/{REPO}" class="hide-sm">GitHub</a>
      <button class="theme-toggle" type="button" id="theme" aria-label="Switch theme">
        {icon("sun", "i-sun")}{icon("moon", "i-moon")}
      </button>
    </nav>
  </div>
</header>

<main id="top">

<div class="hero">
  <div class="wrap">
    <div>
      <span class="eyebrow">No API key</span>
      <h1>Job applications that <em class="hard">can't</em> claim things you haven't done.</h1>
      <p class="lede">{e(data.SUB)}</p>
      <div class="cta-row">
        <a class="btn btn-primary" href="#install">{icon("down")}Install</a>
        <a class="btn btn-ghost" href="#how">See how it works</a>
      </div>
      <p class="hero-note">
        <span>{icon("tick")}Claude Code, Codex, Cursor, Gemini CLI</span>
        <span>{icon("tick")}macOS and Linux</span>
        <span>{icon("tick")}Nothing to install</span>
      </p>
    </div>
    <div>
      {terminal("fit-after.md", data.FIT_OUTPUT)}
      <div class="tree">
        <div class="tree-head">One folder per job</div>
        <ul>{files}</ul>
      </div>
    </div>
  </div>
</div>

<section id="why">
  <div class="wrap">
    <div class="sec-head">
      <div class="kicker">Why this one</div>
      <h2>Every CV tool will happily write you a better career.</h2>
      <p>This one is built so it can't. Three decisions do most of that work.</p>
    </div>
    <div class="reasons rise">{reasons}</div>
  </div>
</section>

<section id="install">
  <div class="wrap">
    <div class="sec-head">
      <div class="kicker">Install</div>
      <h2>Which agent do you use?</h2>
      <p>Pick one and you'll get the exact command. Every route installs the
         same eleven skills — there's no paid tier and nothing to sign up for.</p>
    </div>
    <div class="picker">
      <div class="agents" role="tablist" aria-label="Choose your coding agent">
        {"".join(agent_buttons)}
      </div>
      <div class="panel" id="panel">
        <div class="panel-empty" id="panel-empty">
          <div>{icon("point")}<p>Choose your agent on the left.</p></div>
        </div>
        {panels}
      </div>
    </div>
  </div>
</section>

<section id="skills">
  <div class="wrap">
    <div class="sec-head">
      <div class="kicker">Eleven skills</div>
      <h2>Take all of them, or take one.</h2>
      <p>Each one works on its own — you can install just the guard to check a
         letter you wrote yourself, or just the fit score to decide whether a
         job is worth an evening.</p>
    </div>
    <div class="skills">{"".join(cards)}</div>
  </div>
</section>

<section id="how">
  <div class="wrap">
    <div class="sec-head">
      <div class="kicker">How it works</div>
      <h2>You bring the link. It brings the evidence.</h2>
    </div>
    <ol class="steps rise">
      <li><b>Your CV becomes a profile, once.</b><span>Your agent reads it and
        writes one YAML file. You check that file — and everything after is
        built only from what's in it.</span></li>
      <li><b>The posting gets read properly.</b><span>In the browser you already
        have, because job boards render their descriptions with JavaScript and a
        plain fetch gets a spinner.</span></li>
      <li><b>You find out where you stand before anything is written.</b>
        <span>Including the gaps. If a job needs something you haven't done,
        it says so instead of writing around it.</span></li>
      <li><b>The CV is rebuilt from your own bullets.</b><span>Selected,
        reordered, reworded — never invented. The employers, titles and dates
        are copied across, not generated.</span></li>
      <li><b>Every sentence is checked back against your profile.</b>
        <span>Figures and names that aren't in it get flagged, with the sentence
        they're in, for you to read again.</span></li>
      <li><b>You get the files.</b><span>PDF and markdown, in a folder for that
        job, next to the score and the critique. Nothing is sent.</span></li>
    </ol>
    <div class="proof rise" style="margin-top:40px">
      {terminal("checking a draft", data.GUARD_OUTPUT)}
      {terminal("an honest no", data.ANSWER_OUTPUT)}
    </div>
  </div>
</section>

<section id="faq">
  <div class="wrap">
    <div class="sec-head">
      <div class="kicker">Questions</div>
      <h2>The ones worth asking first.</h2>
    </div>
    <div class="faq">
      <details><summary>Does it apply to jobs for me?</summary>
        <p>No, and it won't be made to. It produces the documents; you send
        them. Some employers disqualify applications the applicant didn't
        write, and that's their call to make.</p></details>
      <details><summary>Do I need an API key or a subscription?</summary>
        <p>No. Your coding agent is the model, so whatever you already pay for
        covers it. There's no provider to sign up to, no token bill, and nothing
        is uploaded anywhere.</p></details>
      <details><summary>Does it scrape LinkedIn?</summary>
        <p>No. LinkedIn walls and throttles automated access and the risk of
        working around that would land on your account. It works out who's worth
        messaging, builds the search, and drafts something specific — you run the
        search and press send.</p></details>
      <details><summary>What do I actually need installed?</summary>
        <p>Python 3.9 or newer, which macOS and every Linux already has, and a
        Chromium-family browser — Chrome, Chromium, Edge or Brave — for reading
        job pages and making PDFs. Without a browser you still get markdown.</p>
        </details>
      <details><summary>Where does my CV go?</summary>
        <p>Into a <code>jobhunt/</code> folder in whatever directory you work in,
        and nowhere else. It never leaves your machine. The repo has three
        separate guards against your own profile being committed to git by
        accident.</p></details>
      <details><summary>Can I just use one skill?</summary>
        <p>Yes — that's what the per-skill downloads are for. Each folder carries
        its own copy of the library and imports nothing from its siblings, so one
        skill installed alone works exactly the same as all eleven.</p></details>
      <details><summary>Will it make my CV good?</summary>
        <p>It will make your CV <em>accurate</em>, and put your strongest
        evidence where a reader meets it. It can't give you experience you don't
        have, and it will tell you plainly when a job needs some.</p></details>
    </div>
  </div>
</section>

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
