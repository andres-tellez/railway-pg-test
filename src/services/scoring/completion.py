"""
Canonical per-run completion-percent producer and V1.6 completed-run threshold.

PHASE_3_IMPLEMENTATION_CHECKLIST 0.B / SMARTCOACH_SYSTEM_SPEC_V1.md §7.

Single-source-of-truth (PHASE_3_IMPLEMENTATION_CHECKLIST §X.5):
    This module is the only place where the ``completion_pct`` formula
    and the V1.6 0.50 "completed" threshold are defined. All per-run
    scoring, weekly ``adherence_runs_pct`` aggregation, and coach
    payload adapters MUST consume these helpers — do NOT inline the
    ``actual / planned * 100`` formula or the ``0.50`` / ``50.0``
    literal at call sites.

Storage/payload contract:
    ``completion_pct`` is ALWAYS stored and surfaced in **percent
    scale (0-100)** where ``100.0`` means exactly planned miles.
    Values may exceed ``100.0`` (overshoot) and are not clipped.
    ``None`` means completion is undefined (no plan, or zero/negative
    planned miles).

Threshold contract (V1.6 §7 "adherence_runs_pct"):
    A run counts as "completed" only when
    ``completion_pct >= COMPLETION_THRESHOLD_PCT`` (50.0, i.e. 50% of
    planned miles). Call ``is_run_completed(activity.completion_pct)``
    rather than inlining the comparison.
"""

from __future__ import annotations

from typing import Optional


COMPLETION_THRESHOLD_RATIO: float = 0.50
"""V1.6 §7 — ratio form of the "run counted as completed" threshold."""

COMPLETION_THRESHOLD_PCT: float = COMPLETION_THRESHOLD_RATIO * 100.0
"""Percent-scale equivalent for comparison against stored ``completion_pct``."""


def compute_completion_pct(
    actual_miles: Optional[float], planned_miles: Optional[float]
) -> Optional[float]:
    """
    Canonical per-run ``completion_pct`` producer.

    Returns the ratio of ``actual_miles`` to ``planned_miles`` expressed
    as a percent (0-100 scale, unclipped on overshoot). Returns ``None``
    when completion is undefined: ``planned_miles`` missing / zero /
    negative, or ``actual_miles`` missing.

    Rounding is the caller's responsibility so DB persistence (2 dp)
    and display surfaces (1 dp) can format independently without this
    helper becoming opinionated about presentation.
    """
    if planned_miles is None or planned_miles <= 0:
        return None
    if actual_miles is None:
        return None
    return (float(actual_miles) / float(planned_miles)) * 100.0


def is_run_completed(completion_pct_value: Optional[float]) -> bool:
    """
    V1.6 §7 completed-run gate.

    Returns ``True`` iff ``completion_pct_value`` is present (not
    ``None``) and at least ``COMPLETION_THRESHOLD_PCT`` (50.0).

    ``None`` returns ``False``: unplanned / zero-planned runs never
    count as "completed" for weekly ``adherence_runs_pct`` purposes.
    They are handled under V1.6 §7 unplanned-run rules.
    """
    if completion_pct_value is None:
        return False
    return float(completion_pct_value) >= COMPLETION_THRESHOLD_PCT
