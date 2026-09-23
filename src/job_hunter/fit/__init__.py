"""How well a CV answers one job, measured before and after tailoring.

Deterministic and explainable on purpose: a score you cannot trace is a score
you cannot act on, and a score a model produces is one more thing to check.
"""

from __future__ import annotations

from . import evidence, report, requirements
from .models import Evidence, FitReport, Requirement
from .report import SKIM_BULLETS, delta, score

__all__ = ["SKIM_BULLETS", "Evidence", "FitReport", "Requirement", "delta",
           "evidence", "report", "requirements", "score"]
