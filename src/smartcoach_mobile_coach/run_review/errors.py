"""Local typed errors for Run Review V2 — never leak outside the package."""

from __future__ import annotations


class RunReviewError(Exception):
    """Base class for run-review errors."""


class RunReviewSkip(RunReviewError):
    """
    Raised before any LLM call when the turn is *not* a completed-run review.

    The orchestrator treats this the same as :class:`RunReviewFallback`: it
    swallows the exception and continues into the legacy fastpath / full
    tool loop. Kept as a distinct type so logs and tests can distinguish
    "intentionally skipped" from "tried and degraded".
    """


class RunReviewFallback(RunReviewError):
    """
    Raised after we have started run-review work but cannot finish cleanly
    (no resolvable run, model returned empty text twice, unexpected
    payload shape, etc.). The orchestrator must continue into the legacy
    path so the user still gets a response.
    """
