"""
Coach ↔ Strava data readiness.

Defines when activity data is complete enough for run-aware coach replies:
sync must be marked complete, and there must be no Run rows in the ingest window
that lack both the Strava detail pass *and* list-level summary fields (distance or
conv_distance, plus moving_time) needed by :class:`coach.data.activity_fetcher.ActivityFetcher`.

Runs with list metadata but ``detail_enriched_at IS NULL`` are allowed: enrichment
adds streams/splits/extra HR zones but the coach already reads distance, pace, and
basic HR from list-ingested columns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from src.db.dao.strava_sync_status_dao import StravaSyncStatusDAO
from src.services.activity_service import (
    count_pending_detail_enrichment,
    count_pending_detail_missing_summary,
)
from src.services.strava_reconciliation_service import compute_strava_six_week_window


@dataclass(frozen=True)
class CoachStravaDataReadiness:
    """Server-side coach Strava readiness for a linked athlete."""

    coach_data_ready: bool
    sync_status: Optional[str]
    pending_detail_enrichment: int


def evaluate_coach_strava_data_readiness(
    session: Session, user_id: str, athlete_id: int
) -> CoachStravaDataReadiness:
    """
    True when sync_status is 'complete' and no Run rows in the ingest window lack
    list-level summary needed for coach (see module doc). ``pending_detail_enrichment``
    still reports rows with a missing detail pass for observability.
    """
    dao = StravaSyncStatusDAO(session)
    row = dao.get_status(user_id, athlete_id)
    sync_st = row.status if row else None
    win = compute_strava_six_week_window()
    pending = count_pending_detail_enrichment(
        session, athlete_id, win.window_after_ts, win.before_ts
    )
    blocking = count_pending_detail_missing_summary(
        session, athlete_id, win.window_after_ts, win.before_ts
    )
    complete = sync_st == "complete"
    ready = complete and blocking == 0
    return CoachStravaDataReadiness(
        coach_data_ready=ready,
        sync_status=sync_st,
        pending_detail_enrichment=pending,
    )
