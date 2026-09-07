"""The FastAPI application.

`web/` is a shell: it reads a form, calls one library function, and renders the
result. Anything that decides something belongs in `profile`, `jobs`, `generate`
or `render` instead - so that the CLI and the UI cannot drift apart.

Every endpoint here is a plain `def`, not `async def`, on purpose. Starlette runs
sync endpoints in a worker thread, and a worker thread has no running event loop,
which is exactly what Playwright's sync API requires. Making these `async` would
break job fetching and PDF export with "sync API inside asyncio loop".
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .. import __version__
from .routes import router
from .templating import templates


def create_app() -> FastAPI:
    app = FastAPI(title="Job Hunter", version=__version__, docs_url=None, redoc_url=None)
    app.include_router(router)

    @app.exception_handler(404)
    def not_found(request, exc) -> HTMLResponse:  # pragma: no cover - display only
        return templates.TemplateResponse(
            request, "error.html",
            {"title": "Not found", "message": "There is nothing at this address."},
            status_code=404,
        )

    return app


app = create_app()
