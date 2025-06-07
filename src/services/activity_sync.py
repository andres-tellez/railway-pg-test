# src/services/activity_sync.py

from datetime import datetime, timedelta
from src.utils.logger import get_logger
from src.services.token_refresh import ensure_fresh_access_token
from src.db.dao.activity_dao import upsert_activities
from src.db.dao.split_dao import upsert_splits
from src.services.strava_client import StravaClient

log = get_logger(__name__)

DEFAULT_PER_PAGE = 200

def sync_recent(session, athlete_id: int, lookback_days: int = 30, max_activities=None) -> int:
    """
    Sync recent activities for a given athlete (last N days).
    Automatically refreshes tokens as needed.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)

    return sync_activities_between(session, athlete_id, start_date, end_date, max_activities)

def sync_full_history(session, athlete_id: int, lookback_days: int = 365, max_activities=None) -> int:
    """
    Sync full historical activities.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)

    return sync_activities_between(session, athlete_id, start_date, end_date, max_activities)

def sync_activities_between(session, athlete_id: int, start_date: datetime, end_date: datetime, max_activities=None) -> int:
    """
    Ingest activities and splits using modern StravaClient.
    """
    access_token = ensure_fresh_access_token(session, athlete_id)
    client = StravaClient(session, athlete_id)

    all_activities = []
    page = 1

    while True:
        activities = client.get_activities(after=int(start_date.timestamp()), before=int(end_date.timestamp()), page=page, per_page=DEFAULT_PER_PAGE)

        if not activities:
            break

        all_activities.extend(activities)

        if max_activities and len(all_activities) >= max_activities:
            all_activities = all_activities[:max_activities]
            break

        if len(activities) < DEFAULT_PER_PAGE:
            break

        page += 1

    if not all_activities:
        log.info(f"No activities found for athlete {athlete_id} between {start_date.date()} and {end_date.date()}")
        return 0

    count = upsert_activities(session, athlete_id, all_activities)
    log.info(f"Synced {count} activities for athlete {athlete_id} between {start_date.date()} and {end_date.date()}")

    # Process splits directly from activity 'laps' field if present
    all_splits = []
    for activity in all_activities:
        splits = extract_splits_from_activity(activity)
        all_splits.extend(splits)

    if all_splits:
        upsert_splits(session, all_splits)
        log.info(f"Synced {len(all_splits)} splits for athlete {athlete_id}")

    return count

def extract_splits_from_activity(activity_json):
    activity_id = activity_json["id"]
    splits_json = activity_json.get("laps", [])

    extracted = []
    for split_obj in splits_json:
        extracted.append({
            "activity_id": activity_id,
            "lap_index": split_obj.get("split_index"),
            "distance": split_obj.get("distance"),
            "elapsed_time": split_obj.get("elapsed_time"),
            "moving_time": split_obj.get("moving_time"),
            "average_speed": split_obj.get("average_speed"),
            "max_speed": split_obj.get("max_speed"),
            "start_index": split_obj.get("start_index"),
            "end_index": split_obj.get("end_index"),
            "split": True,
            "average_heartrate": split_obj.get("average_heartrate"),
            "pace_zone": split_obj.get("pace_zone"),
            "conv_distance": split_obj.get("conv_distance"),
            "conv_avg_speed": split_obj.get("conv_avg_speed"),
            "conv_moving_time": split_obj.get("conv_moving_time"),
            "conv_elapsed_time": split_obj.get("conv_elapsed_time"),
        })
    return extracted
