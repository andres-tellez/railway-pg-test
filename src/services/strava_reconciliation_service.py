"""
Strava ↔ DB reconciliation for the same rolling window used by ingestion.

Compares Strava Run activity IDs against stored activities for the authenticated
user in the canonical ingest window (Monday-based, UTC midnight bounds),
then supports bounded repair via GET /activities/{id} detail fetches.

The window length is ``STRAVA_INGEST_LOOKBACK_WEEKS`` full ISO weeks before the
current week start through "now" (same source as full sync ``after`` timestamp).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone, time as dt_time
from typing import Any, NamedTuple

from sqlalchemy.orm import Session

from src.db.dao.activity_dao import ActivityDAO
from src.db.models.activities import Activity
from src.services.activity_service import ActivityIngestionService
from src.services.strava_access_service import StravaClient
from src.services.token_service import get_valid_token
from src.utils.config import config
from src.utils.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)

# Full sync, reconciliation, and sync-health use this many full ISO weeks back
# from the current week start (Monday 00:00 UTC) for the `after` timestamp.
STRAVA_INGEST_LOOKBACK_WEEKS = 3

MAX_MISSING_IDS_PREVIEW = 50
RECONCILE_RATE_BUFFER = 8
DEFAULT_RECONCILE_MAX_FETCH = 15


class StravaSixWeekWindow(NamedTuple):
    """Ingest/reconciliation window; aligned with `run_full_ingestion_and_enrichment`.

    Field ``six_week_start`` is the UTC Monday 00:00 at the start of the lookback
    window (historical name; span is ``STRAVA_INGEST_LOOKBACK_WEEKS`` weeks).
    """

    current_week_start: date
    six_week_start: date
    six_week_start_dt: datetime
    two_week_cutoff_dt: datetime
    window_after_ts: int
    before_ts: int


def compute_strava_six_week_window() -> StravaSixWeekWindow:
    """UTC week-aligned ingest window: Monday 00:00 UTC − 3 weeks through now_utc."""
    now_utc = datetime.now(timezone.utc)
    today_utc = now_utc.date()
    days_since_monday = today_utc.weekday()  # Monday = 0 (ISO)
    current_week_start_date = today_utc - timedelta(days=days_since_monday)
    window_start_date = current_week_start_date - timedelta(
        weeks=STRAVA_INGEST_LOOKBACK_WEEKS
    )
    window_start_dt = datetime.combine(
        window_start_date, dt_time.min, tzinfo=timezone.utc
    )
    window_after_ts = int(window_start_dt.timestamp())
    before_ts = int(now_utc.timestamp())

    two_week_cutoff_date = current_week_start_date - timedelta(weeks=2)
    two_week_cutoff_dt = datetime.combine(
        two_week_cutoff_date, dt_time.min, tzinfo=timezone.utc
    )

    six_week_start = window_start_date
    six_week_start_dt = window_start_dt

    logger.debug(
        "strava ingest window after_ts=%s before_ts=%s",
        window_after_ts,
        before_ts,
    )
    return StravaSixWeekWindow(
        current_week_start=current_week_start_date,
        six_week_start=six_week_start,
        six_week_start_dt=six_week_start_dt,
        two_week_cutoff_dt=two_week_cutoff_dt,
        window_after_ts=window_after_ts,
        before_ts=before_ts,
    )


def filter_strava_runs_in_six_week_window(
    six_week_start_dt: datetime, activities: list[dict]
) -> list[dict]:
    """Keep Runs whose start_date falls on/after the window start (ingestion parity)."""
    runs_only: list[dict] = []
    for activity in activities:
        start_date_str = activity.get("start_date")
        if not start_date_str:
            runs_only.append(activity)
            continue
        try:
            start_dt = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        except ValueError:
            runs_only.append(activity)
            continue
        if start_dt >= six_week_start_dt:
            runs_only.append(activity)
    logger.debug(
        "filter_strava_runs_in_six_week_window before=%s after=%s",
        len(activities),
        len(runs_only),
    )
    return runs_only


def _strava_run_ids(runs: list[dict]) -> set[int]:
    ids: set[int] = set()
    for a in runs:
        raw = a.get("id") or a.get("activity_id")
        if raw is None:
            continue
        ids.add(int(raw))
    return ids


def db_run_activity_ids_in_window(
    session: Session,
    user_id: Any,
    athlete_id: int,
    six_week_start_dt: datetime,
) -> set[int]:
    rows = (
        session.query(Activity.activity_id)
        .filter(
            Activity.user_id == user_id,
            Activity.athlete_id == athlete_id,
            Activity.type == "Run",
            Activity.start_date >= six_week_start_dt,
        )
        .all()
    )
    return {int(r[0]) for r in rows}


def fetch_strava_runs_for_window(
    session: Session,
    athlete_id: int,
    user_id: Any,
    *,
    per_page: int | None = None,
    after_ts: int | None = None,
    before_ts: int | None = None,
) -> tuple[StravaSixWeekWindow, list[dict]]:
    win = compute_strava_six_week_window()
    use_after = win.window_after_ts if after_ts is None else after_ts
    use_before = win.before_ts if before_ts is None else before_ts
    svc = ActivityIngestionService(session, athlete_id, user_id=user_id)
    fetched = svc.fetch_all_activities(
        after=use_after,
        before=use_before,
        per_page=per_page or config.DEFAULT_PER_PAGE,
        type_filter="Run",
        type_limit=None,
    )
    runs = filter_strava_runs_in_six_week_window(win.six_week_start_dt, fetched)
    return win, runs


def build_sync_health_payload(
    session: Session,
    athlete_id: int,
    user_id: Any,
    *,
    per_page: int | None = None,
) -> dict[str, Any]:
    win, runs = fetch_strava_runs_for_window(
        session, athlete_id, user_id, per_page=per_page
    )
    strava_ids = _strava_run_ids(runs)
    db_ids = db_run_activity_ids_in_window(
        session, user_id, athlete_id, win.six_week_start_dt
    )
    missing_sorted = sorted(strava_ids - db_ids)
    extra_sorted = sorted(db_ids - strava_ids)
    preview = missing_sorted[:MAX_MISSING_IDS_PREVIEW]
    return {
        "windowStart": win.six_week_start_dt.isoformat(),
        "windowEnd": datetime.fromtimestamp(win.before_ts, tz=timezone.utc).isoformat(),
        "stravaRunCount": len(strava_ids),
        "dbRunCountInWindow": len(db_ids),
        "missingCount": len(missing_sorted),
        "missingIdsPreview": preview,
        "missingIdsTruncated": len(missing_sorted) > len(preview),
        "reconciledOk": len(missing_sorted) == 0,
        "dbOnlyNotInStravaCount": len(extra_sorted),
    }


def reconcile_missing_runs(
    session: Session,
    athlete_id: int,
    user_id: Any,
    *,
    max_fetch: int = DEFAULT_RECONCILE_MAX_FETCH,
    per_page: int | None = None,
) -> dict[str, Any]:
    win, runs = fetch_strava_runs_for_window(
        session, athlete_id, user_id, per_page=per_page
    )
    strava_ids = _strava_run_ids(runs)
    db_ids = db_run_activity_ids_in_window(
        session, user_id, athlete_id, win.six_week_start_dt
    )
    missing_sorted = sorted(strava_ids - db_ids)
    cap = max(0, min(int(max_fetch), 50))
    to_fetch = missing_sorted[:cap]

    rate_limiter = get_rate_limiter()
    stats = rate_limiter.get_stats()
    remaining = stats.get("remaining_15min", 0)
    needed = len(to_fetch)
    if needed > 0 and remaining < needed + RECONCILE_RATE_BUFFER:
        wait_seconds = max(float(stats.get("wait_time_seconds", 0)), 60.0)
        return {
            "deferred": True,
            "reason": "rate_limit_headroom",
            "missingCount": len(missing_sorted),
            "attempted": 0,
            "upserted": 0,
            "waitSecondsSuggested": int(wait_seconds),
            "remaining15Min": remaining,
            "neededWithBuffer": needed + RECONCILE_RATE_BUFFER,
        }

    if not to_fetch:
        return {
            "deferred": False,
            "missingCount": 0,
            "attempted": 0,
            "upserted": 0,
        }

    access_token = get_valid_token(session, athlete_id)
    client = StravaClient(access_token)
    upserted = 0
    errors: list[dict[str, Any]] = []

    for aid in to_fetch:
        try:
            raw = client.get_activity(aid)
        except Exception as exc:  # pragma: no cover - network/API variance
            logger.warning("Reconcile: failed to fetch activity %s: %s", aid, exc)
            errors.append({"activityId": aid, "error": str(exc)})
            continue
        if raw.get("type") != "Run":
            continue
        row = dict(raw)
        row["activity_id"] = row.pop("id", None) or row.get("activity_id")
        row["user_id"] = user_id
        try:
            n = ActivityDAO.upsert_activities(
                session, athlete_id, [row], user_id=user_id
            )
            upserted += int(n)
        except Exception as exc:  # pragma: no cover
            logger.warning("Reconcile: upsert failed for %s: %s", aid, exc)
            errors.append({"activityId": aid, "error": str(exc)})

    return {
        "deferred": False,
        "missingCount": len(missing_sorted),
        "attempted": len(to_fetch),
        "upserted": upserted,
        "errors": errors,
    }
