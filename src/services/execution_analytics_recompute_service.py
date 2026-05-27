"""
Recompute Tier 2 execution KPIs on activities (ingest, profile refresh, backfill).
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.db.models.activities import Activity
from src.smartcoach_mobile_coach.execution_analytics.producer import (
    refresh_activity_execution_kpis,
)

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_timers: Dict[str, threading.Timer] = {}

DEFAULT_LOOKBACK_DAYS = 21
DEFAULT_PROFILE_LOOKBACK_WEEKS = 52


def _debounce_seconds() -> float:
    raw = os.getenv("EXECUTION_RECOMPUTE_DEBOUNCE_SEC", "120")
    try:
        value = float(raw)
        return max(5.0, min(value, 3600.0))
    except ValueError:
        return 120.0


def _profile_lookback_weeks() -> int:
    raw = os.getenv(
        "EXECUTION_RECOMPUTE_WINDOW_WEEKS", str(DEFAULT_PROFILE_LOOKBACK_WEEKS)
    )
    try:
        return max(1, min(int(raw), 104))
    except ValueError:
        return DEFAULT_PROFILE_LOOKBACK_WEEKS


def _recent_lookback_days() -> int:
    raw = os.getenv("EXECUTION_RECOMPUTE_RECENT_DAYS", str(DEFAULT_LOOKBACK_DAYS))
    try:
        return max(1, min(int(raw), 365))
    except ValueError:
        return DEFAULT_LOOKBACK_DAYS


def _activity_ids_in_window(
    session: Session,
    *,
    user_id: str,
    athlete_id: int | None,
    after_ts: int | None,
    before_ts: int | None,
    limit: int,
) -> list[int]:
    query = session.query(Activity.activity_id).filter(
        Activity.user_id == user_id,
        Activity.type == "Run",
    )
    if athlete_id is not None:
        query = query.filter(Activity.athlete_id == athlete_id)
    if after_ts is not None:
        query = query.filter(
            Activity.start_date >= datetime.fromtimestamp(after_ts, tz=timezone.utc)
        )
    if before_ts is not None:
        query = query.filter(
            Activity.start_date <= datetime.fromtimestamp(before_ts, tz=timezone.utc)
        )
    rows = query.order_by(Activity.start_date.desc()).limit(max(1, int(limit))).all()
    return [int(row.activity_id) for row in rows]


def recompute_execution_kpis_for_window(
    session: Session,
    *,
    user_id: str,
    athlete_id: int | None = None,
    after_ts: int | None = None,
    before_ts: int | None = None,
    limit: int = 200,
    commit: bool = True,
) -> int:
    """Synchronously recompute execution KPIs for runs in a Strava sync window."""
    activity_ids = _activity_ids_in_window(
        session,
        user_id=user_id,
        athlete_id=athlete_id,
        after_ts=after_ts,
        before_ts=before_ts,
        limit=limit,
    )
    if not activity_ids:
        return 0
    return refresh_activity_execution_kpis(
        session,
        user_id,
        activity_ids=activity_ids,
        commit=commit,
    )


def recompute_recent_execution_kpis(
    session: Session,
    user_id: str,
    *,
    days: int | None = None,
    commit: bool = True,
) -> int:
    lookback = days if days is not None else _recent_lookback_days()
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback)
    rows = (
        session.query(Activity.activity_id)
        .filter(
            Activity.user_id == user_id,
            Activity.type == "Run",
            Activity.start_date >= cutoff,
        )
        .order_by(Activity.start_date.desc())
        .all()
    )
    activity_ids = [int(row.activity_id) for row in rows]
    if not activity_ids:
        return 0
    return refresh_activity_execution_kpis(
        session,
        user_id,
        activity_ids=activity_ids,
        commit=commit,
    )


def recompute_stale_execution_kpis_for_user(
    session: Session,
    user_id: str,
    *,
    lookback_weeks: int | None = None,
    commit: bool = True,
) -> int:
    """
    Recompute stale execution KPIs after profile refresh or backfill.

    Uses ``execution_zone_profile_at`` / version staleness. Optional lookback
    limits candidate runs to a recent window (weeks).
    """
    weeks = lookback_weeks if lookback_weeks is not None else _profile_lookback_weeks()
    if weeks >= 104:
        return refresh_activity_execution_kpis(session, user_id, commit=commit)

    cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    rows = (
        session.query(Activity.activity_id)
        .filter(
            and_(
                Activity.user_id == user_id,
                Activity.type == "Run",
                Activity.start_date >= cutoff,
            )
        )
        .order_by(Activity.activity_id)
        .all()
    )
    activity_ids = [int(row.activity_id) for row in rows]
    if not activity_ids:
        return 0
    return refresh_activity_execution_kpis(
        session,
        user_id,
        activity_ids=activity_ids,
        commit=commit,
    )


def _run_post_activity_recompute(user_id: str) -> None:
    from src.db.db_session import get_session

    session = get_session()
    try:
        updated = recompute_recent_execution_kpis(session, user_id)
        logger.info(
            "Post-activity execution recompute user=%s… updated=%s",
            user_id[:8],
            updated,
        )
    except Exception:
        logger.exception(
            "Post-activity execution recompute failed user=%s…", user_id[:8]
        )
    finally:
        session.close()
        with _lock:
            _timers.pop(user_id, None)


def schedule_post_activity_execution_recompute(user_id: str) -> None:
    """Debounced recompute after activity upserts (coalesces burst uploads)."""
    if os.getenv("EXECUTION_RECOMPUTE_ON_ACTIVITY", "1").strip() in (
        "0",
        "false",
        "False",
        "no",
        "No",
    ):
        return
    uid = str(user_id)
    delay = _debounce_seconds()

    def _fire() -> None:
        _run_post_activity_recompute(uid)

    with _lock:
        old = _timers.pop(uid, None)
        if old is not None:
            old.cancel()
        timer = threading.Timer(delay, _fire)
        timer.daemon = True
        _timers[uid] = timer
        timer.start()


def _run_profile_refresh_recompute(user_id: str) -> None:
    from src.db.db_session import get_session

    session = get_session()
    try:
        updated = recompute_stale_execution_kpis_for_user(session, user_id)
        logger.info(
            "Profile refresh execution recompute user=%s… updated=%s",
            user_id[:8],
            updated,
        )
    except Exception:
        logger.exception(
            "Profile refresh execution recompute failed user=%s…", user_id[:8]
        )
    finally:
        session.close()


def schedule_profile_refresh_execution_recompute(user_id: str) -> None:
    """Debounced stale recompute after runner_zone_profiles changes."""
    if os.getenv("EXECUTION_RECOMPUTE_ON_PROFILE_REFRESH", "1").strip() in (
        "0",
        "false",
        "False",
        "no",
        "No",
    ):
        return
    uid = str(user_id)

    def _fire() -> None:
        _run_profile_refresh_recompute(uid)

    delay = _debounce_seconds()
    timer = threading.Timer(delay, _fire)
    timer.daemon = True
    timer.start()
