"""
After a successful Strava ingestion, backfill ``weekly_training_insights`` for
up to six **completed** Mon–Sun weeks (oldest → newest) plus one **in_progress**
pass for the **calendar week containing today** so mid-week connections get a
current-week row.

Runs in a daemon thread so ingestion HTTP/workers are not blocked.

Disable with ``WEEKLY_INSIGHT_INGESTION_BACKFILL=0``.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def _backfill_enabled() -> bool:
    return os.getenv("WEEKLY_INSIGHT_INGESTION_BACKFILL", "1").strip() not in (
        "0",
        "false",
        "False",
        "no",
        "No",
    )


def _run_backfill(user_id: str) -> None:
    from src.db.db_session import get_session
    from src.smartcoach_mobile_coach.weekly_insights_service import (
        generate_weekly_insight,
        last_completed_week_bounds,
    )

    session = get_session()
    try:
        today = date.today()
        last_completed_monday, _ = last_completed_week_bounds(today)
        oldest_completed_monday = last_completed_monday - timedelta(weeks=5)

        for i in range(6):
            week_monday = oldest_completed_monday + timedelta(weeks=i)
            ref_date = week_monday + timedelta(days=7)
            result = generate_weekly_insight(
                session,
                user_id,
                ref_date=ref_date,
                insight_week="completed",
            )
            logger.debug(
                "Ingestion backfill completed-week user=%s… week=%s generated=%s skipped=%s",
                user_id[:8],
                week_monday.isoformat(),
                result.get("generated"),
                result.get("skipped"),
            )

        in_prog = generate_weekly_insight(
            session,
            user_id,
            ref_date=today,
            insight_week="in_progress",
        )
        logger.info(
            "Ingestion backfill done user=%s… in_progress generated=%s skipped=%s",
            user_id[:8],
            in_prog.get("generated"),
            in_prog.get("skipped"),
        )
    except Exception:
        logger.exception(
            "Weekly insight ingestion backfill failed user=%s…", user_id[:8]
        )
    finally:
        session.close()


def schedule_weekly_insights_after_strava_ingestion(
    user_id: str,
    *,
    force_full_sync: bool,
    inserted_count: int,
) -> None:
    """
    Schedule backfill when ingestion likely brought new Strava data.

    Runs when ``force_full_sync`` is true or at least one activity row was
    inserted, and ``WEEKLY_INSIGHT_INGESTION_BACKFILL`` is enabled.
    """
    if not user_id or not _backfill_enabled():
        return
    if not force_full_sync and inserted_count <= 0:
        return

    uid = str(user_id)
    t = threading.Thread(target=_run_backfill, args=(uid,), daemon=True)
    t.start()
