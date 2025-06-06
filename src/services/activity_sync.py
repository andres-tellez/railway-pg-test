# src/services/activity_sync.py

from datetime import datetime, timedelta
from src.utils.logger import get_logger
from src.services.strava import fetch_activities_between
from src.db.dao.activity_dao import upsert_activities
from src.db.dao.split_dao import upsert_splits
from src.services.split_extraction import extract_splits

log = get_logger(__name__)

def sync_recent(session, athlete_id: int, access_token: str = None, per_page=200, max_activities=None) -> int:
    """
    Sync recent activities for a given athlete.
    Automatically refreshes tokens if access_token is not provided or expired.
    """
    try:
        # 🔑 If access_token not provided, refresh it automatically
        if not access_token:
            access_token = ensure_fresh_access_token(session, athlete_id)

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)

        return sync_activities_between(
            session, athlete_id, access_token, start_date, end_date, per_page, max_activities
        )

    except Exception as e:
        raise RuntimeError(f"Failed to sync recent activities: {e}")


def sync_full_history(session, athlete_id: int, access_token: str = None, lookback_days: int = 365, per_page=200, max_activities=None) -> int:
    """
    Sync full historical activities, auto-refreshing tokens if needed.
    """
    try:
        if not access_token:
            access_token = ensure_fresh_access_token(session, athlete_id)

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=lookback_days)

        return sync_activities_between(
            session, athlete_id, access_token, start_date, end_date, per_page, max_activities
        )

    except Exception as e:
        raise RuntimeError(f"Failed to sync full history for athlete {athlete_id}: {e}")


def sync_activities_between(session, athlete_id: int, access_token: str, start_date: datetime, end_date: datetime, per_page=200, max_activities=None) -> int:
    """
    Core ingestion logic (unchanged).
    """
    try:
        all_activities = []
        page = 1

        while True:
            activities = fetch_activities_between(access_token, start_date, end_date, per_page=per_page)
            if not activities:
                break

            all_activities.extend(activities)

            if max_activities and len(all_activities) >= max_activities:
                all_activities = all_activities[:max_activities]
                break

            if len(activities) < per_page:
                break

            page += 1

        if not all_activities:
            log.info(f"No activities found for athlete {athlete_id} between {start_date.date()} and {end_date.date()}")
            return 0

        count = upsert_activities(session, athlete_id, all_activities)
        log.info(f"Synced {count} activities for athlete {athlete_id} between {start_date.date()} and {end_date.date()}")

        all_splits = []
        for activity in all_activities:
            splits = extract_splits(activity)
            all_splits.extend(splits)

        if all_splits:
            upsert_splits(session, all_splits)
            log.info(f"Synced {len(all_splits)} splits for athlete {athlete_id}")

        return count

    except Exception as e:
        raise RuntimeError(f"Failed to fetch or persist activities: {e}")
