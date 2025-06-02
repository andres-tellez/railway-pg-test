from datetime import datetime, timedelta
import json
from src.utils.logger import get_logger
from src.services.strava import fetch_activities_between
from src.db.dao.activity_dao import upsert_activities

log = get_logger(__name__)


def sync_recent_activities(session, athlete_id, access_token, per_page=20) -> int:
    """
    Download recent activities from Strava and persist them.
    Limited to the past 7 days for initial sync validation.
    """
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)  # Narrow window for MVP validation
        activities = fetch_activities_between(access_token, start_date, end_date, per_page)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch recent activities: {e}")

    if not activities:
        log.info(f"No recent activities for athlete {athlete_id}")
        return 0

    try:
        count = upsert_activities(session, athlete_id, activities)
        log.info(f"Inserted {count} recent activities for athlete {athlete_id}")
        return count
    except Exception as e:
        raise RuntimeError(f"Failed to persist activities: {e}")


def sync_activities_between(session, athlete_id: int, access_token: str, start_date: datetime, end_date: datetime, per_page=20) -> int:
    """
    Fetch and store activities for a given athlete between the specified dates.
    This remains available for future enrichment and backfill use cases.
    """
    try:
        activities = fetch_activities_between(access_token, start_date, end_date, per_page)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch activities between dates: {e}")

    if not activities:
        log.info(f"No activities found for athlete {athlete_id} between {start_date.date()} and {end_date.date()}")
        return 0

    try:
        count = upsert_activities(session, athlete_id, activities)
        log.info(f"Synced {count} activities for athlete {athlete_id}")
        return count
    except Exception as e:
        raise RuntimeError(f"Failed to persist activities: {e}")


def enrich_missing_activities(session, athlete_id):
    """
    Placeholder enrichment function.
    Will be implemented fully during enrichment pipeline phase.
    """
    log.info("Enriching activities is not yet implemented in MVP.")
    return 0
