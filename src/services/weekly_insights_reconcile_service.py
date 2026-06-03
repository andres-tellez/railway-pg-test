"""
Centralized weekly Insights projection reconcile for one user.

Refreshes execution KPIs on recent runs, then upserts ``weekly_training_insights``
for completed calendar weeks plus optional in-progress week. Idempotent and safe
to call from ingestion, profile save, and scripts.

Disable async scheduling with ``WEEKLY_INSIGHT_INGESTION_BACKFILL=0`` (legacy env name).
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_timers: Dict[str, threading.Timer] = {}

_DEFAULT_WEEKS = 6
_DEFAULT_DEBOUNCE_SEC = 120.0


def reconcile_enabled() -> bool:
    return os.getenv("WEEKLY_INSIGHT_INGESTION_BACKFILL", "1").strip() not in (
        "0",
        "false",
        "False",
        "no",
        "No",
    )


def _debounce_seconds() -> float:
    raw = os.getenv("WEEKLY_INSIGHT_RECONCILE_DEBOUNCE_SEC", str(_DEFAULT_DEBOUNCE_SEC))
    try:
        value = float(raw)
        return max(5.0, min(value, 3600.0))
    except ValueError:
        return _DEFAULT_DEBOUNCE_SEC


def _week_result_entry(
    week_start: date,
    result: Dict[str, Any],
    *,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    generated = bool(result.get("generated")) if error is None else False
    return {
        "week_start": week_start.isoformat(),
        "generated": generated,
        "skipped": not generated and error is None,
        "reason": result.get("reason") if error is None else None,
        "error": error,
    }


def ensure_user_weekly_insights(
    session: Session,
    user_id: str,
    *,
    weeks: int = _DEFAULT_WEEKS,
    include_current_week: bool = True,
    execution_lookback_weeks: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Make weekly Insights projection current for the standard window.

    1. Recompute stale execution KPIs on recent runs.
    2. Upsert weekly_training_insights for completed weeks (oldest → newest).
    3. Optionally upsert the calendar week containing today (in_progress).
    """
    from src.services.execution_analytics_recompute_service import (
        recompute_stale_execution_kpis_for_user,
    )
    from src.smartcoach_mobile_coach.weekly_insights_service import (
        generate_weekly_insight,
        last_completed_week_bounds,
    )

    uid = str(user_id)
    weeks = max(1, min(int(weeks), 12))
    lookback = (
        execution_lookback_weeks if execution_lookback_weeks is not None else weeks
    )

    summary = {"generated": 0, "skipped": 0, "errors": 0}
    completed_weeks: List[Dict[str, Any]] = []
    in_progress_entry: Optional[Dict[str, Any]] = None

    execution_runs_updated = recompute_stale_execution_kpis_for_user(
        session,
        uid,
        lookback_weeks=lookback,
    )

    today = date.today()
    last_completed_monday, _ = last_completed_week_bounds(today)
    oldest_completed_monday = last_completed_monday - timedelta(weeks=weeks - 1)

    for i in range(weeks):
        week_monday = oldest_completed_monday + timedelta(weeks=i)
        ref_date = week_monday + timedelta(days=7)
        try:
            result = generate_weekly_insight(
                session,
                uid,
                ref_date=ref_date,
                insight_week="completed",
            )
            entry = _week_result_entry(week_monday, result)
            if entry["generated"]:
                summary["generated"] += 1
            elif entry["error"] is None:
                summary["skipped"] += 1
        except Exception as exc:
            summary["errors"] += 1
            completed_weeks.append(
                _week_result_entry(week_monday, {}, error=str(exc)),
            )
            logger.exception(
                "Weekly reconcile completed-week failed user=%s… week=%s",
                uid[:8],
                week_monday.isoformat(),
            )
            continue
        completed_weeks.append(entry)

    if include_current_week:
        try:
            in_prog_result = generate_weekly_insight(
                session,
                uid,
                ref_date=today,
                insight_week="in_progress",
            )
            in_progress_entry = _week_result_entry(today, in_prog_result)
            if in_progress_entry["generated"]:
                summary["generated"] += 1
            elif in_progress_entry["error"] is None:
                summary["skipped"] += 1
        except Exception as exc:
            summary["errors"] += 1
            in_progress_entry = _week_result_entry(today, {}, error=str(exc))
            logger.exception("Weekly reconcile in_progress failed user=%s…", uid[:8])

    payload = {
        "user_id": uid,
        "execution_runs_updated": execution_runs_updated,
        "completed_weeks": completed_weeks,
        "in_progress": in_progress_entry,
        "summary": summary,
    }
    logger.info(
        "Weekly insights reconcile user=%s… execution_updated=%s summary=%s",
        uid[:8],
        execution_runs_updated,
        summary,
    )
    return payload


def _run_scheduled_reconcile(
    user_id: str,
    *,
    weeks: int,
    include_current_week: bool,
) -> None:
    from src.db.db_session import get_session

    session = get_session()
    try:
        ensure_user_weekly_insights(
            session,
            user_id,
            weeks=weeks,
            include_current_week=include_current_week,
        )
    except Exception:
        logger.exception(
            "Scheduled weekly insights reconcile failed user=%s…", user_id[:8]
        )
    finally:
        session.close()
        with _lock:
            _timers.pop(str(user_id), None)


def schedule_ensure_user_weekly_insights(
    user_id: str,
    *,
    weeks: int = _DEFAULT_WEEKS,
    include_current_week: bool = True,
) -> None:
    """Schedule debounced reconcile in a daemon thread (non-blocking for HTTP)."""
    if not user_id or not reconcile_enabled():
        return

    uid = str(user_id)
    delay = _debounce_seconds()

    def _fire() -> None:
        _run_scheduled_reconcile(
            uid,
            weeks=weeks,
            include_current_week=include_current_week,
        )

    with _lock:
        old = _timers.pop(uid, None)
        if old is not None:
            old.cancel()
        timer = threading.Timer(delay, _fire)
        timer.daemon = True
        _timers[uid] = timer
        timer.start()
