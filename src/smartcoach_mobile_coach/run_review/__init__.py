"""
Run Review V2 — focused completed-run review module.

Public API (the only seam the rest of the app should depend on):

- ``should_use_run_review_v2(...)`` — cheap gate; returns ``True`` only when the
  feature flag is on **and** the request looks like a completed-run review.
- ``handle_run_review_turn(...)`` — one-shot handler that gathers a
  ``RunReviewContext`` (facts, KPIs, splits, plan-derived workout intent),
  builds a small additive system prompt, makes one LLM call, and returns the
  same ``run_summary`` envelope the mobile app already renders.

Design rules (enforced by file boundaries, not lint):

1. The LLM does coaching reasoning. The server only gathers context.
2. No deterministic verdict strings ("productive tempo run", etc.) are
   produced here. The prompt provides framing constraints only.
3. Every failure raises :class:`RunReviewFallback` so the orchestrator can
   continue into the legacy fastpath / full tool loop without disruption.
4. Nothing under ``run_review/`` is imported elsewhere; only this module
   exports the public symbols. See ``orchestrator/__init__.py`` for the
   single integration point.

Feature flag: ``SMARTCOACH_RUN_REVIEW_V2`` (see :mod:`.config`).
"""

from __future__ import annotations

from src.smartcoach_mobile_coach.run_review.errors import (
    RunReviewError,
    RunReviewFallback,
    RunReviewSkip,
)
from src.smartcoach_mobile_coach.run_review.entry import (
    handle_run_review_turn,
    should_use_run_review_v2,
)

__all__ = [
    "RunReviewError",
    "RunReviewFallback",
    "RunReviewSkip",
    "handle_run_review_turn",
    "should_use_run_review_v2",
]
