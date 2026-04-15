"""
Admin-triggered batch refresh for ``weekly_training_insights`` (mobile Insights tab).

Refreshes:
1. The **latest completed** Mon–Sun week (same window as the Sunday cron / ``generate_weekly_insights.py``).
2. The **current calendar week** via ``insight_week="in_progress"`` (Mon through today for KPIs).

Only users with at least one easy run in the respective date window are processed.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Literal

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


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

    last_start, last_end = last_completed_week_bounds(today)
    ref_completed = last_start + timedelta(days=7)
    users_completed = get_users_with_easy_runs(session, last_start, last_end)
    completed_stats = _process_users(
        session,
        users_completed,
        ref_date=ref_completed,
        insight_week="completed",
        label="completed",
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
        "last_completed_week": {
            "week_start": str(last_start),
            "week_end": str(last_end),
            "users_considered": len(users_completed),
            **completed_stats,
        },
        "current_week_in_progress": {
            "week_start": str(cur_start),
            "week_end": str(cur_end),
            "kpi_end": str(kpi_end),
            "users_considered": len(users_in_progress),
            **in_progress_stats,
        },
    }
