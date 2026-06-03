"""
After a successful Strava ingestion, schedule weekly Insights reconcile for the user.

Runs in a debounced daemon thread so ingestion HTTP/workers are not blocked.

Disable with ``WEEKLY_INSIGHT_INGESTION_BACKFILL=0``.
"""

from __future__ import annotations

import logging

from src.services.weekly_insights_reconcile_service import (
    reconcile_enabled,
    schedule_ensure_user_weekly_insights,
)

logger = logging.getLogger(__name__)


def schedule_weekly_insights_after_strava_ingestion(
    user_id: str,
    *,
    force_full_sync: bool,
    inserted_count: int,
) -> None:
    """
    Schedule reconcile when ingestion likely brought new Strava data.

    Runs when ``force_full_sync`` is true or at least one activity row was
    inserted, and ``WEEKLY_INSIGHT_INGESTION_BACKFILL`` is enabled.
    """
    if not user_id or not reconcile_enabled():
        return
    if not force_full_sync and inserted_count <= 0:
        return

    schedule_ensure_user_weekly_insights(str(user_id))
