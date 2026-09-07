"""The web UI: a thin shell over the library.

`app` is exported here so `uvicorn job_hunter.web:app` finds the application
rather than the module of the same name.
"""

from __future__ import annotations

from .app import app, create_app

__all__ = ["app", "create_app"]
