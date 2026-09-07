"""All the routes, in two files: pages that show things, actions that change them."""

from __future__ import annotations

from fastapi import APIRouter

from . import actions, pages

router = APIRouter()
router.include_router(pages.router)
router.include_router(actions.router)

__all__ = ["router"]
