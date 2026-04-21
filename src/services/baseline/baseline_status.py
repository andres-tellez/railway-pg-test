"""
Canonical producer for V1.6 §12 ``baseline_status`` enum.

PHASE_3_IMPLEMENTATION_CHECKLIST §X.5 single-source-of-truth: this
module is the ONLY place in the codebase that derives
``baseline_status``. The Phase B ``get_user_context()`` tool (3B.10),
the plan generator's baseline-fallback branch, and the §16 weekly
adaptation pass MUST all call the adapter below — never reimplement
the three-band classification, never mirror it on mobile, and never
let the LLM override it (V1.6 §19: LLM must not derive, override, or
contradict deterministic fields).

Spec reference (SMARTCOACH_SYSTEM_SPEC_V1.md §12)
-------------------------------------------------
Three-value enum keyed off **run count** and **distinct-weeks-with-
runs** in the last 4 weeks of activity history:

* ``insufficient`` — ``< 2 weeks`` of data **OR** ``< 3 runs`` in
  the last 4 weeks. Beginner baseline, no compression, conservative
  start.
* ``thin`` — ``2-3 weeks`` of data **OR** ``3-5 runs`` in the last
  4 weeks. Conservative baseline; no compression; begin refining
  after week 2.
* ``strong`` — ``>= 4 weeks`` of continuous data **AND** ``>= 6
  runs`` in the last 4 weeks. Full baseline; compression allowed
  if §13 criteria also met.

Logic cascade (most restrictive wins)
-------------------------------------
1. ``insufficient`` if ``weeks < 2`` OR ``runs < 3``.
2. Otherwise ``strong`` if ``weeks >= 4`` AND ``runs >= 6``.
3. Otherwise ``thin`` (the natural middle band covering 2-3 weeks
   of data or 3-5 runs).

This ordering is correctness-sensitive — ``insufficient`` must be
checked first so a runner with 4 weeks but only 2 runs (≥ 2 weeks
of data, but runs < 3) correctly lands in ``insufficient`` rather
than ``thin``.

Week-bucketing semantics
------------------------
"Distinct weeks in the last 4 weeks" is computed as rolling 7-day
buckets relative to ``today``: a run is assigned to
``bucket = (today - activity_date).days // 7`` giving integer
buckets in ``[0, 4)``. Distinct buckets with at least one run are
counted, max 4. This is deterministic, free of ISO-week boundary
artefacts (year rollover, locale-dependent week starts), and
matches the "last 4 weeks" spec wording without overloading the
calendar-week concept used elsewhere. Activities strictly older
than 28 days are excluded; same-day runs (bucket 0) count.

Derivation policy — on-read, not persisted
------------------------------------------
``baseline_status`` is recomputed each time a caller asks for it,
using the current activity history and the current ``today``. This
mirrors the §12 dynamic-updates clause ("recomputed each week when
the weekly adaptation pass runs") without the write-invalidation
problems persisting the value would introduce: as "today" advances
and old weeks roll out of the window, a previously ``strong``
baseline can legitimately weaken, and we want the next read to
reflect that rather than stale state.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.activities import Activity


class BaselineStatus(str, Enum):
    """V1.6 §12 three-value enum. ``str`` base makes JSON serialization trivial."""

    INSUFFICIENT = "insufficient"
    THIN = "thin"
    STRONG = "strong"


# Window length for "last 4 weeks" (spec §12).
BASELINE_WINDOW_DAYS = 28
# Number of 7-day buckets inside the window. Cap on distinct-weeks count.
BASELINE_WINDOW_WEEKS = 4


def classify_baseline_status(
    *,
    runs_in_last_4_weeks: int,
    weeks_with_runs_in_last_4: int,
) -> BaselineStatus:
    """
    Pure classification function — no I/O, no ORM access.

    Applies the spec §12 three-band cascade to two already-computed
    counts. Caller is responsible for producing the counts using the
    same window semantics documented in the module docstring (rolling
    7-day buckets over the last 28 days).

    Args:
        runs_in_last_4_weeks: Number of ``Run``-typed activities in
            the 28-day window. Must be non-negative.
        weeks_with_runs_in_last_4: Distinct 7-day buckets (0-4
            inclusive) within the window that contain at least one
            run. Callers must clamp to ``[0, 4]``; values outside
            this range indicate a window-bucket bug.

    Returns:
        :class:`BaselineStatus` — never ``None`` (spec mandates a
        value every time the weekly adaptation pass runs; the
        ``insufficient`` band is the explicit "not enough data"
        state rather than an absent field).
    """
    # Defensive clamp — keeps the contract intact if a caller mis-
    # counts (e.g. passes negative values from an off-by-one window
    # computation). We don't raise: the safe-default behavior is
    # "treat it as insufficient" rather than crashing the coach.
    runs = max(0, int(runs_in_last_4_weeks))
    weeks = max(0, min(BASELINE_WINDOW_WEEKS, int(weeks_with_runs_in_last_4)))

    # Cascade: most-restrictive first. See module docstring.
    if weeks < 2 or runs < 3:
        return BaselineStatus.INSUFFICIENT
    if weeks >= BASELINE_WINDOW_WEEKS and runs >= 6:
        return BaselineStatus.STRONG
    return BaselineStatus.THIN


def count_runs_and_weeks_in_window(
    activity_dates: Iterable[date],
    *,
    today: date,
    window_days: int = BASELINE_WINDOW_DAYS,
) -> tuple[int, int]:
    """
    Bucket a sequence of activity dates into the spec §12 window.

    Separated from :func:`classify_baseline_status` so it can be
    unit-tested independently and reused by the weekly adaptation
    pass (§16) or any future plan-generator baseline-fallback
    caller that already has activity dates in hand.

    Args:
        activity_dates: Iterable of ``date`` values (one per Run
            activity). ``datetime`` inputs are NOT accepted here —
            convert at the call site to keep the window math
            timezone-explicit.
        today: Reference ``date`` for the window's upper bound
            (exclusive above, inclusive for same-day runs).
        window_days: Window size in days (default 28 = 4 weeks).
            Exposed for tests; production callers should keep the
            default to stay spec-aligned.

    Returns:
        ``(runs_in_window, distinct_weeks_with_runs)`` — both
        non-negative; weeks count is clamped to ``[0, window_days //
        7]``.
    """
    window_weeks = window_days // 7
    earliest = today - timedelta(days=window_days - 1)
    runs_in_window = 0
    buckets_seen: set[int] = set()
    for activity_date in activity_dates:
        if activity_date is None:
            continue
        if activity_date < earliest or activity_date > today:
            continue
        runs_in_window += 1
        day_offset = (today - activity_date).days
        bucket = day_offset // 7
        if 0 <= bucket < window_weeks:
            buckets_seen.add(bucket)
    return runs_in_window, len(buckets_seen)


def compute_baseline_status_for_athlete(
    session: Session,
    athlete_id: int,
    *,
    today: Optional[date] = None,
) -> BaselineStatus:
    """
    Adapter — the canonical entry point for server-side callers.

    Queries ``activities`` for the athlete's Run-typed activities in
    the last 28 days, derives ``(runs, distinct_weeks)`` via
    :func:`count_runs_and_weeks_in_window`, and dispatches to
    :func:`classify_baseline_status`. Same-day activities count;
    activities strictly older than 28 days are excluded.

    Args:
        session: SQLAlchemy session bound to the activities schema.
        athlete_id: Target athlete (activities are keyed by athlete,
            not user — resolve via ``user_athlete_links`` at the
            tool/route boundary).
        today: Reference date for the window. Defaults to
            ``datetime.now(timezone.utc).date()``. Tests should pass
            an explicit value to keep assertions deterministic.

    Returns:
        :class:`BaselineStatus`.
    """
    if today is None:
        today = datetime.now(timezone.utc).date()

    window_start = datetime.combine(
        today - timedelta(days=BASELINE_WINDOW_DAYS - 1), datetime.min.time()
    )
    stmt = select(Activity.start_date).where(
        Activity.athlete_id == athlete_id,
        Activity.type == "Run",
        Activity.start_date >= window_start,
    )
    rows = session.execute(stmt).all()
    activity_dates: list[date] = []
    for (start_dt,) in rows:
        if start_dt is None:
            continue
        # ``start_date`` is a ``DateTime`` column; reduce to date in
        # the reference frame of ``today`` (naive UTC) so bucketing
        # is consistent with the window boundary. V1.7 note: same
        # TZ caveat as ``violated_rest_day`` — a future activity
        # ``local_date`` column will sharpen cross-midnight edge
        # cases, but the baseline counts are robust to one-day
        # misalignment on rare boundary runs.
        activity_dates.append(start_dt.date())

    runs, weeks = count_runs_and_weeks_in_window(activity_dates, today=today)
    return classify_baseline_status(
        runs_in_last_4_weeks=runs,
        weeks_with_runs_in_last_4=weeks,
    )
