"""One headless browser, shared by every source that needs a real page.

`jobs.fetch` loads a single posting; these sources load result lists. Both need
the same things - a Chromium that announces itself like a browser, a timeout
that fails with advice rather than a stack trace - so that part lives here.

Playwright's sync API refuses to run inside a running event loop, so async
callers must wrap these in `asyncio.to_thread`, exactly as they do for `fetch`.
"""

from __future__ import annotations

from typing import Any

from ...jobs.fetch import USER_AGENT

TIMEOUT = 30

#: Result lists are built client-side on every board worth searching, so the
#: page needs a moment after load before its cards exist.
SETTLE_MS = 2500


class BrowserError(RuntimeError):
    """The page could not be read. Carries what the user should do instead."""


def read(url: str, script: str, *, timeout: int = TIMEOUT,
         settle_ms: int = SETTLE_MS, wait_for: str = "") -> Any:
    """Open `url`, run `script` in the page, return whatever it evaluates to."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise BrowserError("Searching needs Playwright: pip install playwright") from exc

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                raise BrowserError(
                    "Could not start Chromium. Run: playwright install chromium"
                ) from exc
            try:
                page = browser.new_page(user_agent=USER_AGENT, locale="en-US")
                page.set_default_timeout(timeout * 1000)
                page.goto(url, wait_until="domcontentloaded")
                if wait_for:
                    try:
                        page.wait_for_selector(wait_for, timeout=timeout * 1000)
                    except PlaywrightError:
                        # No cards is a real answer - an empty search, or a wall.
                        # The caller decides which, from what the script returns.
                        pass
                page.wait_for_timeout(settle_ms)
                return page.evaluate(script)
            finally:
                browser.close()
    except BrowserError:
        raise
    except Exception as exc:
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        if "timeout" in first.lower():
            raise BrowserError(f"{url} did not finish loading in time.") from exc
        raise BrowserError(f"Could not load {url}: {first}") from exc
