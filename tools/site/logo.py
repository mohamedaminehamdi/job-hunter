"""The mark.

Two sheets: the one behind is your profile, the one in front is the CV built
for this job, tilted as if just pulled off the stack. That is the whole product
in two rectangles, and it survives being 16 pixels wide - which a document icon
with text lines on it does not.

Drawn here rather than kept as a file so the colours follow the theme and the
favicon can be built from the same shape.
"""

#: One 24x24 grid, used at every size.
BACK = "M7.6 3.4h8.2a2.4 2.4 0 0 1 2.4 2.4v10.6"
FRONT_D = ("M6.2 6.6h9.1a2.2 2.2 0 0 1 2.2 2.2v9.9a2.2 2.2 0 0 1-2.2 2.2H6.2"
           "A2.2 2.2 0 0 1 4 18.7V8.8a2.2 2.2 0 0 1 2.2-2.2Z")
TICK = "M7.9 13.6l2.6 2.6 5.1-5.1"


def mark(size=24, tone="currentColor", accent=None, cls=""):
    """The lockup's symbol. `accent` colours the tick when there is room."""
    accent = accent or tone
    klass = f' class="{cls}"' if cls else ""
    return (
        f'<svg{klass} width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" aria-hidden="true">'
        # the profile behind, open on two sides so it reads as a second sheet
        f'<path d="{BACK}" stroke="{tone}" stroke-width="1.7" '
        f'stroke-linecap="round" opacity=".42"/>'
        # the tailored one in front
        f'<path d="{FRONT_D}" stroke="{tone}" stroke-width="1.7"/>'
        f'<path d="{TICK}" stroke="{accent}" stroke-width="1.9" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg>")


def favicon(ink="%23ffffff", ground="%2312664a"):
    """The same shape as a data URI, filled so it reads in a browser tab."""
    return (
        "data:image/svg+xml,"
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<rect width='24' height='24' rx='6' fill='{ground}'/>"
        f"<path d='{FRONT_D}' fill='none' stroke='{ink}' stroke-width='1.8'/>"
        f"<path d='{TICK}' fill='none' stroke='{ink}' stroke-width='2' "
        "stroke-linecap='round' stroke-linejoin='round'/>"
        "</svg>")
