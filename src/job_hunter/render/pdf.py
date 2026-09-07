"""HTML to PDF, via the browser that is already a dependency.

Chromium's own print pipeline, so what a PDF looks like is what the HTML looks
like - no second layout engine to keep happy. `set_content` rather than a
`data:` URL: it has no length limit and needs no escaping.

Playwright's sync API cannot run inside a running event loop, so async callers
must use `asyncio.to_thread`.
"""

from __future__ import annotations

from pathlib import Path


class PdfError(RuntimeError):
    """The PDF could not be produced. Message is addressed to the user."""


def write_pdf(html: str, path: Path) -> Path:
    """Render `html` to a PDF at `path`, creating parent directories."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise PdfError("Making a PDF needs Playwright: pip install playwright") from exc

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                raise PdfError(
                    "Could not start Chromium. Run: playwright install chromium"
                ) from exc
            try:
                page = browser.new_page()
                page.set_content(html, wait_until="load")
                # Print styles, not screen styles: @page margins come from the CSS.
                page.emulate_media(media="print")
                page.pdf(path=str(path), format="A4", print_background=True,
                         prefer_css_page_size=True)
            finally:
                browser.close()
    except PdfError:
        raise
    except Exception as exc:
        raise PdfError(f"Could not render the PDF: {exc}") from exc

    if not path.exists() or path.stat().st_size == 0:
        raise PdfError(f"The PDF at {path} came out empty.")
    return path
