"""
Admin-triggered batch refresh for ``weekly_training_insights`` (mobile Insights tab).

Refreshes:
1. The **six most recent completed** Mon–Sun weeks (oldest → newest; same span as
   post–Strava ingestion backfill), for users with easy runs in each week.
2. The **current calendar week** via ``insight_week="in_progress"`` (Mon through today).

Only users with at least one easy run in the respective date window are processed
per week.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Literal

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_NUM_COMPLETED_WEEKS = 6


def _process_users(
    session: Session,
    user_ids: List[str],
    *,
    ref_date: date,
    insight_week: Literal["completed", "in_progress"],
    label: str,
) -> Dict[str, int]:
    from src.smartcoach_mobile_coach.weekly_insights_service import (
        generate_weekly_insight,
    )

    generated = 0
    skipped = 0
    errors = 0
    for uid in user_ids:
        try:
            result = generate_weekly_insight(
                session,
                uid,
                ref_date=ref_date,
                insight_week=insight_week,
            )
            if result.get("generated"):
                generated += 1
            else:
                skipped += 1
        except Exception:
            errors += 1
            logger.exception(
                "Admin weekly insights batch: %s failed for user %s…",
                label,
                uid[:8],
            )
    return {"generated": generated, "skipped": skipped, "errors": errors}


def run_weekly_insights_admin_batch(session: Session) -> Dict[str, Any]:
    from src.smartcoach_mobile_coach.weekly_insights_service import (
        calendar_week_containing,
        get_users_with_easy_runs,
        last_completed_week_bounds,
    )

    today = date.today()

    last_completed_monday, _last_completed_sunday = last_completed_week_bounds(today)
    oldest_completed_monday = last_completed_monday - timedelta(
        weeks=_NUM_COMPLETED_WEEKS - 1
    )

    week_summaries: List[Dict[str, Any]] = []
    six_totals = {"generated": 0, "skipped": 0, "errors": 0}

    for i in range(_NUM_COMPLETED_WEEKS):
        week_monday = oldest_completed_monday + timedelta(weeks=i)
        week_sunday = week_monday + timedelta(days=6)
        ref_date = week_monday + timedelta(days=7)
        users = get_users_with_easy_runs(session, week_monday, week_sunday)
        stats = _process_users(
            session,
            users,
            ref_date=ref_date,
            insight_week="completed",
            label=f"completed_week_{week_monday.isoformat()}",
        )
        for k in six_totals:
            six_totals[k] += stats[k]
        week_summaries.append(
            {
                "week_start": str(week_monday),
                "week_end": str(week_sunday),
                "ref_date": str(ref_date),
                "users_considered": len(users),
                **stats,
            }
        )

    cur_start, cur_end = calendar_week_containing(today)
    kpi_end = min(today, cur_end)
    users_in_progress = get_users_with_easy_runs(session, cur_start, kpi_end)
    in_progress_stats = _process_users(
        session,
        users_in_progress,
        ref_date=today,
        insight_week="in_progress",
        label="in_progress",
    )

    return {
        "six_completed_weeks": {
            "oldest_week_start": str(oldest_completed_monday),
            "newest_week_start": str(last_completed_monday),
            "weeks": week_summaries,
            "totals": six_totals,
        },
        "current_week_in_progress": {
            "week_start": str(cur_start),
            "week_end": str(cur_end),
            "kpi_end": str(kpi_end),
            "users_considered": len(users_in_progress),
            **in_progress_stats,
        },
    }
