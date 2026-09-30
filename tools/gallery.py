#!/usr/bin/env python3
"""Render every corpus profile every way, for eyes.

The tests say what can be read off a page. Whether the page looks right is a
judgement, so this writes the pages somewhere a person - or a CI artifact -
can open them: HTML at each density, the markdown, the LaTeX source, and a
PDF through each renderer the machine has, fitted to its budget.

    python tools/gallery.py out/gallery
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
import jobhunt as jh  # noqa: E402

CORPUS = ROOT / "tests" / "corpus"


def main(argv):
    out = Path(argv[0] if argv else "gallery")
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(CORPUS.glob("*.yaml")):
        profile = jh.load(jh.Profile, path)
        stem = path.stem
        for density in jh.DENSITIES:
            (out / f"{stem}-{density}.html").write_text(
                jh.cv_html(profile, density=density), encoding="utf-8")
        (out / f"{stem}.md").write_text(jh.cv_markdown(profile), encoding="utf-8")
        (out / f"{stem}.tex").write_text(jh.cv_latex(profile), encoding="utf-8")
        for how, present in (("browser", jh.find_browser()), ("latex", jh.find_tex())):
            if not present:
                rows.append(f"| {stem} | {how} | - | not on this machine | | |")
                continue
            try:
                made = jh.export(profile, out / f"{stem}-{how}.pdf", fit=True,
                                 prefer="browser" if how == "browser" else None)
            except jh.PdfError as exc:
                rows.append(f"| {stem} | {how} | failed | | | {exc} |")
                continue
            rows.append(f"| {stem} | {how} | {made.pages} | {made.budget} | {made.density} "
                        f"| {'; '.join(made.trimmed) or '-'} |")
    index = ("# Gallery\n\nEvery corpus profile, rendered. Open the PDFs; the table is "
             "what the tool itself measured.\n\n"
             "| profile | renderer | pages | budget | density | trimmed to fit |\n"
             "|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n")
    (out / "index.md").write_text(index, encoding="utf-8")
    print(index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
