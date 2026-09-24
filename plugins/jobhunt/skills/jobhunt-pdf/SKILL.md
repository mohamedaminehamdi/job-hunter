---
name: jobhunt-pdf
description: >
  Render a tailored CV or cover letter to a PDF and a markdown file, using the
  browser already on the machine. Use after a CV or letter has been built and
  someone needs the file to attach.
allowed-tools: Bash, Read
---

# Render it

```bash
python3 pdf.py <run>/cv.yaml
python3 pdf.py <run>/letter.yaml
python3 pdf.py <run>/letter.yaml --theme "#7b2ff7"   # the company's colour
```

`--theme` takes `neutral`, `classic` (serif), or a hex colour. A posting's own
colour is read off its page and stored in `job.yaml` as `brand_color`.

No install. It drives Chrome, Chromium, Edge or Brave - whichever is there.
`JOBHUNT_BROWSER` points at one in an unusual place.

## Two things worth knowing

**The markdown is written first, always.** If the PDF step fails - no browser,
or a browser that will not start - the markdown is still there and still
sendable. Say that rather than treating it as a failure, and **do not write the
markdown yourself as a workaround**: it is rendered from `cv.yaml`, and writing
it by hand hands the employers, titles and dates back to you.

**A document with a blocking issue does not become a file.** Unfilled
placeholder text, a missing name: it exits 2 and names what to fix. That is the
door where "nothing becomes a PDF until it is fit to send" is actually kept, so
do not route around it.
