"""
Coach ↔ Strava data readiness.

Defines when activity data is complete enough for run-aware coach replies:
sync must be marked complete and all Run rows in the ingest window must have
detail enrichment recorded (detail_enriched_at IS NOT NULL).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from src.db.dao.strava_sync_status_dao import StravaSyncStatusDAO
from src.services.activity_service import count_pending_detail_enrichment
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
    True when sync_status is 'complete' and no pending detail enrichment in the
    canonical ingest window (same bounds as count uses for orchestration).
    """
    dao = StravaSyncStatusDAO(session)
    row = dao.get_status(user_id, athlete_id)
    sync_st = row.status if row else None
    win = compute_strava_six_week_window()
    pending = count_pending_detail_enrichment(
        session, athlete_id, win.window_after_ts, win.before_ts
    )
    complete = sync_st == "complete"
    ready = complete and pending == 0
    return CoachStravaDataReadiness(
        coach_data_ready=ready,
        sync_status=sync_st,
        pending_detail_enrichment=pending,
    )
