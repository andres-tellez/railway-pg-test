"""
Deterministic recent-run stats for coach-facing Strava status.

Uses the same 28-day window and 7-day bucket semantics as
``baseline_status`` (V1.6 §12) via
:func:`src.services.baseline.baseline_status.count_runs_and_weeks_in_window`.
Activities are filtered with ``type == "Run"`` and ``user_id`` to match
how ``/api/strava/status`` counts total activities.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.activities import Activity
from src.services.baseline.baseline_status import (
    BASELINE_WINDOW_DAYS,
    count_runs_and_weeks_in_window,
)


def compute_recent_run_rollup_for_user(
    session: Session,
    user_id: UUID | str,
    *,
    today: Optional[date] = None,
) -> dict[str, Any]:
    """
    Aggregate Run activities in the last 28 days for the given user.

    Returns:
        ``runs_28d``, ``weeks_with_runs_28d`` (distinct 7-day buckets),
        ``longest_run_meters_28d`` (``None`` if no run has a finite distance).
    """
    if today is None:
        today = datetime.now(timezone.utc).date()

    window_start = datetime.combine(
        today - timedelta(days=BASELINE_WINDOW_DAYS - 1),
        datetime.min.time(),
    )
    stmt = select(Activity.start_date, Activity.distance).where(
        Activity.user_id == user_id,
        Activity.type == "Run",
        Activity.start_date >= window_start,
    )
    rows = session.execute(stmt).all()

    activity_dates: list[date] = []
    distances_in_window: list[float] = []

    earliest = today - timedelta(days=BASELINE_WINDOW_DAYS - 1)
    for start_dt, distance in rows:
        if start_dt is None:
            continue
        activity_date = start_dt.date()
        if activity_date < earliest or activity_date > today:
            continue
        activity_dates.append(activity_date)
        if distance is not None:
            d = float(distance)
            if d == d and d > 0.0:  # finite, positive (excludes NaN)
                distances_in_window.append(d)

    runs_28d, weeks_with_runs_28d = count_runs_and_weeks_in_window(
        activity_dates, today=today
    )

    longest_run_meters_28d: Optional[float]
    if distances_in_window:
        longest_run_meters_28d = max(distances_in_window)
    else:
        longest_run_meters_28d = None

    return {
        "runs_28d": runs_28d,
        "weeks_with_runs_28d": weeks_with_runs_28d,
        "longest_run_meters_28d": longest_run_meters_28d,
    }
