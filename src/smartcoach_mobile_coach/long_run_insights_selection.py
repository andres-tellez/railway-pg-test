"""
Long-run selection for Insights ``systems.long`` weekly history (v1).

Does not add ``insights_system = 'long'`` on activities. Picks at most one run per
calendar week for the aerobic long trend slice.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    RUN_TYPE_LONG,
    RUN_TYPE_RACE,
    normalize_run_type_key,
)

LONG_RUN_MIN_MOVING_TIME_SEC = 75 * 60
LONG_INFER_MEDIAN_PADDING_SEC = 20 * 60
LONG_INFER_MEDIAN_MULTIPLIER = 1.25


@dataclass(frozen=True)
class LongRunCandidate:
    activity_id: int
    moving_time: int | None
    insights_system: str | None
    matched_run_type_key: str | None
    date_plan_run_type_key: str | None
    planned_type: str | None
    executed_type: str | None
    hr_drift_pct: float | None
    avg_pace_min_per_mi: float | None
    avg_hr_bpm: float | None

    @classmethod
    def from_row(cls, row: Any) -> LongRunCandidate:
        return cls(
            activity_id=int(row.activity_id),
            moving_time=_safe_int(getattr(row, "moving_time", None)),
            insights_system=_optional_str(getattr(row, "insights_system", None)),
            matched_run_type_key=_optional_str(
                getattr(row, "matched_run_type_key", None)
            ),
            date_plan_run_type_key=_optional_str(
                getattr(row, "date_plan_run_type_key", None)
            ),
            planned_type=_optional_str(getattr(row, "planned_type", None)),
            executed_type=_optional_str(getattr(row, "executed_type", None)),
            hr_drift_pct=_safe_float(getattr(row, "hr_drift_pct", None)),
            avg_pace_min_per_mi=_safe_float(getattr(row, "avg_pace", None)),
            avg_hr_bpm=_safe_float(getattr(row, "avg_hr", None)),
        )

    def effective_planned_run_type_key(self) -> str | None:
        for raw in (
            self.matched_run_type_key,
            self.date_plan_run_type_key,
            self.planned_type,
        ):
            norm = normalize_run_type_key(raw)
            if norm:
                return norm
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _normalized_type(value: str | None) -> str | None:
    if not value:
        return None
    return normalize_run_type_key(value)


def is_race_candidate(candidate: LongRunCandidate) -> bool:
    for raw in (
        candidate.matched_run_type_key,
        candidate.date_plan_run_type_key,
        candidate.planned_type,
        candidate.executed_type,
    ):
        if _normalized_type(raw) == RUN_TYPE_RACE:
            return True
    return False


def is_easy_aerobic_candidate(candidate: LongRunCandidate) -> bool:
    return (candidate.insights_system or "").strip().lower() == "easy"


def qualifies_planned_long_run(candidate: LongRunCandidate) -> bool:
    if is_race_candidate(candidate):
        return False
    if candidate.effective_planned_run_type_key() != RUN_TYPE_LONG:
        return False
    mt = candidate.moving_time
    return mt is not None and mt >= LONG_RUN_MIN_MOVING_TIME_SEC


def _median_duration_seconds(durations: Sequence[int]) -> float | None:
    if not durations:
        return None
    return float(statistics.median(durations))


def _meaningfully_longer_than_other_easy_runs(
    longest: LongRunCandidate,
    other_easy: Sequence[LongRunCandidate],
) -> bool:
    mt = longest.moving_time
    if mt is None or mt < LONG_RUN_MIN_MOVING_TIME_SEC:
        return False
    other_durations = [
        c.moving_time
        for c in other_easy
        if c.moving_time is not None and c.activity_id != longest.activity_id
    ]
    median_other = _median_duration_seconds(other_durations)
    if median_other is None:
        return False
    if mt >= LONG_INFER_MEDIAN_MULTIPLIER * median_other:
        return True
    if mt >= median_other + LONG_INFER_MEDIAN_PADDING_SEC:
        return True
    return False


def infer_long_run_candidate(
    candidates: Iterable[LongRunCandidate],
) -> LongRunCandidate | None:
    """Rule 2: longest easy week run that is >=75m and clearly longer than other easy runs."""
    pool = [
        c
        for c in candidates
        if is_easy_aerobic_candidate(c) and not is_race_candidate(c)
    ]
    if not pool:
        return None
    longest = max(pool, key=lambda c: c.moving_time or 0)
    others = [c for c in pool if c.activity_id != longest.activity_id]
    if not _meaningfully_longer_than_other_easy_runs(longest, others):
        return None
    return longest


def select_long_run_for_week(
    candidates: Iterable[LongRunCandidate],
) -> LongRunCandidate | None:
    """Return the canonical long run for one calendar week, or None."""
    items = list(candidates)
    planned = [c for c in items if qualifies_planned_long_run(c)]
    if planned:
        return max(planned, key=lambda c: c.moving_time or 0)
    return infer_long_run_candidate(items)
