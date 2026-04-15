"""
Debounced refresh of ``weekly_training_insights`` for the **current calendar week**
after Run activities are persisted (ingestion, webhooks, reconciliation).

Uses ``generate_weekly_insight(..., insight_week="in_progress")`` so mid-week
runs update the same ``week_start`` row until Sunday batch finalizes.

Disable with env ``WEEKLY_INSIGHT_REFRESH_ON_ACTIVITY=0``.
Debounce seconds: ``WEEKLY_INSIGHT_POST_ACTIVITY_DEBOUNCE_SEC`` (default 120).
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import date
from typing import Dict

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_timers: Dict[str, threading.Timer] = {}


def _debounce_seconds() -> float:
    raw = os.getenv("WEEKLY_INSIGHT_POST_ACTIVITY_DEBOUNCE_SEC", "120")
    try:
        v = float(raw)
        return max(5.0, min(v, 3600.0))
    except ValueError:
        return 120.0


def _refresh_enabled() -> bool:
    return os.getenv("WEEKLY_INSIGHT_REFRESH_ON_ACTIVITY", "1").strip() not in (
        "0",
        "false",
        "False",
        "no",
        "No",
    )


def _run_in_progress_insight(user_id: str) -> None:
    try:
        from src.db.db_session import get_session
        from src.smartcoach_mobile_coach.weekly_insights_service import (
            generate_weekly_insight,
        )

        session = get_session()
        try:
            result = generate_weekly_insight(
                session,
                user_id,
                ref_date=date.today(),
                insight_week="in_progress",
            )
            if result.get("generated"):
                logger.info(
                    "Post-activity weekly insight refreshed (in_progress) user=%s…",
                    user_id[:8],
                )
            else:
                logger.debug(
                    "Post-activity weekly insight skipped user=%s… reason=%s",
                    user_id[:8],
                    result.get("reason", "?"),
                )
        finally:
            session.close()
    except Exception:
        logger.exception(
            "Post-activity weekly insight refresh failed user=%s…", user_id[:8]
        )
    finally:
        with _lock:
            _timers.pop(user_id, None)


def schedule_post_activity_weekly_insight_refresh(user_id: str) -> None:
    """
    Schedule a debounced in-progress weekly insight recompute for ``user_id``.

    Safe to call after every activity upsert batch; coalesces to one run per user.
    """
    if not _refresh_enabled():
        return
    uid = str(user_id)
    delay = _debounce_seconds()

    def _fire() -> None:
        _run_in_progress_insight(uid)

    with _lock:
        old = _timers.pop(uid, None)
        if old is not None:
            old.cancel()
        t = threading.Timer(delay, _fire)
        t.daemon = True
        _timers[uid] = t
        t.start()
