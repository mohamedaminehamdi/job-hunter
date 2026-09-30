---
name: jobhunt-pdf
description: >
  Render a tailored CV or cover letter to a PDF and a markdown file - through
  LaTeX where a TeX engine is installed, through the browser otherwise. Use
  after a CV or letter has been built and someone needs the file to attach.
allowed-tools: Bash, Read
---

# Render it

```bash
python3 pdf.py <run>/cv.yaml
python3 pdf.py <run>/letter.yaml --theme "#7b2ff7"   # the company's colour
python3 pdf.py <run>/cv.yaml --template plain        # a named LaTeX template
python3 pdf.py <run>/cv.yaml --template mine.tex     # your own
python3 pdf.py <run>/cv.yaml --browser               # force the browser
```

`--theme` takes `neutral`, `classic` (serif), or a hex colour. A posting's own
colour is read off its page and stored in `job.yaml` as `brand_color`.

## Which renderer runs

**LaTeX, if a TeX engine is installed.** That is the default and needs no
flag. It is what most people expect a CV to be set in, and a warm compile is
about a quarter of a second - several times faster than the browser.

**The browser, if there is no engine.** Not a failure and not silent: the
result says `"rendered": "browser"`, and you should pass that on. A machine
with Python and a browser remains enough to use this, which is the point of
the project - nothing here installs a toolchain for anybody.

Engines are looked for in this order: `tectonic`, `xelatex`, `lualatex`,
`pdflatex`, then MacTeX's and TeX Live's usual folders. `JOBHUNT_TEX` points
at one somewhere unusual. `JOBHUNT_BROWSER` does the same for the browser.

**`--template` is an instruction, not a preference.** Naming one that is not
installed fails rather than quietly falling back to the browser, because a
browser PDF is not what was asked for. A path must end in `.tex`; a built-in
name is one of `plain`, `plain-letter`.

## Two things worth knowing about LaTeX here

**The first tectonic run is slow** - it downloads its package bundle, which
took 104 seconds on the machine this was written on. Every run after is under
a second. If someone reports the first CV hanging, that is what it is; say so
rather than letting them kill it.

**The templates are deliberately plain.** `geometry`, `enumitem`, `xcolor`,
`hyperref`, `textcomp` - packages that ship with every TeX installation, so
the same template compiles under tectonic, xelatex, lualatex and pdflatex. A
template needing `fontawesome` or a bespoke class is a template that fails on
somebody else's machine. If you write one, keep to that.

## Two things worth knowing either way

**The markdown is written first, always.** If the PDF step fails - no browser,
or a browser that will not start - the markdown is still there and still
sendable. Say that rather than treating it as a failure, and **do not write the
markdown yourself as a workaround**: it is rendered from `cv.yaml`, and writing
it by hand hands the employers, titles and dates back to you.

**A document with no name does not become a file.** It exits 2 and says so.
