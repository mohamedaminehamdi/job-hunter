"""Getting the text of a job posting off the web.

Deterministic: no model runs here. A headless browser loads the page, the
obvious page furniture is removed, and the readable text comes back with the
document title. Whether that text is a job posting is `jobs.parse`'s problem.

A browser rather than an HTTP request because most boards (Greenhouse, Lever,
Workday, LinkedIn) render the description client-side; plain HTML gets you a
loading spinner.

Playwright's sync API refuses to run inside a running event loop, so async
callers - the web layer - must wrap `fetch` in `asyncio.to_thread`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

#: Any scheme, with or without the slashes - `javascript:` must not become a host.
_HAS_SCHEME = re.compile(r"^[a-z][a-z0-9+.\-]*:", re.IGNORECASE)

#: A host with no dot in it is a typo - "notaurl" - with these exceptions, which
#: are how you point the tool at a page served on your own machine.
_LOCAL_HOSTS = frozenset({"localhost", "::1"})

#: Below this, whatever we scraped is a cookie banner or a login wall.
MIN_TEXT = 400
DEFAULT_TIMEOUT = 30

#: Boards serve a stripped page to anything that announces itself as a bot.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

#: Read from the live DOM, not a clone: `innerText` needs layout, and a detached
#: node silently degrades to `textContent`, which loses every line break - so the
#: furniture is removed from the page itself, which we are about to close anyway.
_EXTRACT_JS = """
() => {
  const junk = 'script,style,noscript,svg,iframe,template,nav,footer,aside,form,' +
               '[aria-hidden="true"],[role="navigation"],[role="banner"]';
  document.querySelectorAll(junk).forEach((n) => n.remove());
  for (const selector of ['main', 'article', '[role="main"]', '#content', 'body']) {
    const el = document.querySelector(selector);
    if (!el) continue;
    const text = (el.innerText || '')
      .replace(/[ \\t]+\\n/g, '\\n')
      .replace(/\\n{3,}/g, '\\n\\n')
      .trim();
    if (text.length > 600 || selector === 'body') return text;
  }
  return '';
}
"""

#: The company's colour, for the branded cover letter. `theme-color` when the site
#: declares one, otherwise the fill of the first clearly-coloured button. Greys and
#: near-white/near-black are skipped: they are chrome, not a brand.
_BRAND_JS = """
() => {
  const meta = document.querySelector('meta[name="theme-color"]');
  const hex = (n) => n.toString(16).padStart(2, '0');
  const fromRgb = (value) => {
    const m = (value || '').match(/rgba?\\(([^)]+)\\)/);
    if (!m) return '';
    const [r, g, b, a] = m[1].split(',').map((x) => parseFloat(x));
    if (a !== undefined && a < 0.6) return '';
    const hi = Math.max(r, g, b), lo = Math.min(r, g, b);
    if (hi - lo < 25 || hi > 245 || hi < 20) return '';
    return '#' + hex(r) + hex(g) + hex(b);
  };
  if (meta && meta.content) {
    const declared = meta.content.trim();
    if (/^#[0-9a-f]{3,6}$/i.test(declared)) return declared;
    const converted = fromRgb(declared);
    if (converted) return converted;
  }
  const selector = 'button, .btn, [class*="button"], [class*="Button"], header a';
  for (const el of document.querySelectorAll(selector)) {
    const style = getComputedStyle(el);
    const found = fromRgb(style.backgroundColor) || fromRgb(style.color);
    if (found) return found;
  }
  return '';
}
"""

#: Phrases that mean "we served you a wall, not the job".
_WALLS = (
    "sign in to continue", "log in to continue", "please enable javascript",
    "verify you are human", "are you a robot", "access denied",
    "unusual traffic", "captcha",
)


class FetchError(RuntimeError):
    """The page could not be read. Message is addressed to the user."""


@dataclass
class PageSource:
    url: str
    #: Document title. Often "Job Title - Company", which the parser uses as a hint.
    title: str
    text: str
    #: Hex colour read off the page, or empty. Never a model's guess.
    brand_color: str = ""


def normalise_url(url: str) -> str:
    """Accept what people actually paste, reject what we cannot fetch.

    A bare `example.com/jobs/1` becomes https. Anything that is not http(s) -
    a `file://` path, a `javascript:` URL - is refused rather than opened.
    """
    candidate = url.strip().strip("<>").rstrip(".,")
    if not candidate:
        raise FetchError("No URL given.")
    if not _HAS_SCHEME.match(candidate):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https"):
        raise FetchError(f"Only http and https URLs can be fetched, not {parsed.scheme!r}.")
    host = (parsed.hostname or "").lower()
    if not parsed.netloc or ("." not in host and host not in _LOCAL_HOSTS):
        raise FetchError(f"{url!r} does not look like a web address.")
    return candidate


def fetch(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> PageSource:
    """Load a job page and return its readable text.

    Raises `FetchError` - with what the user should do instead - for a bad URL,
    a missing browser, a page that will not load, or a page that loads but
    yields no description.
    """
    target = normalise_url(url)
    title, text, brand = _render(target, timeout)
    _check(target, text)
    return PageSource(url=target, title=title.strip(), text=text, brand_color=brand)


def _render(url: str, timeout: int) -> tuple[str, str, str]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise FetchError("Fetching a job page needs Playwright: pip install playwright") from exc

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                raise FetchError(
                    "Could not start Chromium. Run: playwright install chromium"
                ) from exc
            try:
                page = browser.new_page(user_agent=USER_AGENT, locale="en-US")
                page.set_default_timeout(timeout * 1000)
                page.goto(url, wait_until="domcontentloaded")
                # Client-rendered boards fill the description in after load, and
                # networkidle never settles on pages with analytics polling.
                page.wait_for_timeout(2000)
                # Brand colour first: extracting the text strips the buttons it
                # reads, and the styles they carry, out of the document.
                brand = page.evaluate(_BRAND_JS) or ""
                return page.title(), page.evaluate(_EXTRACT_JS), brand
            finally:
                browser.close()
    except FetchError:
        raise
    except Exception as exc:
        raise FetchError(f"Could not load {url}: {_reason(exc)}") from exc


def _reason(exc: Exception) -> str:
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    if "timeout" in text.lower():
        return "the page did not finish loading in time"
    return text


def _check(url: str, text: str) -> None:
    """Refuse text that is too thin to be a posting, saying why."""
    if not text.strip():
        raise FetchError(
            f"{url} returned no readable text. Paste the job description instead."
        )
    lowered = text.lower()
    if wall := next((w for w in _WALLS if w in lowered), None):
        if len(text) < MIN_TEXT * 4:
            raise FetchError(
                f"{url} is behind a login or bot check (it says {wall!r}). "
                "Open it in your browser and paste the job description instead."
            )
    if len(text) < MIN_TEXT:
        raise FetchError(
            f"Only {len(text)} characters came back from {url} - not enough to be a "
            "job description. Paste the description text instead."
        )
