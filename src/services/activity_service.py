import time
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.services.token_service import get_valid_token
from src.db.dao.split_dao import upsert_splits
from src.db.dao.activity_dao import upsert_activities
from src.services.strava_access_service import StravaClient
from src.utils.logger import get_logger
import src.utils.config as config

log = get_logger(__name__)
log.setLevel(logging.INFO)

# Constants (can be migrated to config.py if needed later)
DEFAULT_BATCH_SIZE = 20
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_PER_PAGE = 200

# --- Unit conversion helpers ---
def meters_to_miles(meters):
    return round(meters / 1609.344, 2) if meters else None

def meters_to_feet(meters):
    return round(meters * 3.28084, 1) if meters else None

def mps_to_min_per_mile(mps):
    return round(26.8224 / mps, 2) if mps and mps > 0 else None

def format_seconds_to_hms(seconds):
    if seconds is None:
        return None
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02}:{sec:02}" if hours > 0 else f"{minutes}:{sec:02}"

def get_activities_to_enrich(session, athlete_id, limit):
    result = session.execute(
        text("""
            SELECT activity_id FROM activities
            WHERE athlete_id = :athlete_id
            ORDER BY start_date DESC
            LIMIT :limit
        """),
        {"athlete_id": athlete_id, "limit": limit}
    )
    return [row.activity_id for row in result.fetchall()]

def enrich_one_activity(session, access_token, activity_id):
    try:
        client = StravaClient(access_token)
        activity_json = client.get_activity(activity_id)
        zones_data = client.get_hr_zones(activity_id)

        hr_zone_pcts = extract_hr_zone_percentages(zones_data) or [0.0] * 5
        update_activity_enrichment(session, activity_id, activity_json, hr_zone_pcts)

        splits = extract_splits(activity_json, activity_id)
        if splits:
            upsert_splits(session, splits)
            log.info(f"✅ Synced {len(splits)} splits for activity {activity_id}")

        log.info(f"✅ Enriched activity {activity_id}")
        return True

    except Exception as e:
        log.error(f"🔥 Exception while enriching {activity_id}: {e}")
        return True

def enrich_one_activity_with_refresh(session, athlete_id, activity_id):
    try:
        access_token = get_valid_token(session, athlete_id)
        return enrich_one_activity(session, access_token, activity_id)
    except Exception as e:
        log.error(f"Failed enrichment for activity {activity_id}: {e}")
        return True

def update_activity_enrichment(session, activity_id, activity_json, hr_zone_pcts):
    distance_meters = activity_json.get("distance")
    elevation_meters = activity_json.get("total_elevation_gain")
    avg_speed_mps = activity_json.get("average_speed")
    max_speed_mps = activity_json.get("max_speed")
    moving_time_sec = activity_json.get("moving_time")
    elapsed_time_sec = activity_json.get("elapsed_time")

    conv_distance_miles = meters_to_miles(distance_meters)
    conv_elevation_feet = meters_to_feet(elevation_meters)
    conv_avg_speed = mps_to_min_per_mile(avg_speed_mps)
    conv_max_speed = mps_to_min_per_mile(max_speed_mps)
    conv_moving_time = format_seconds_to_hms(moving_time_sec)
    conv_elapsed_time = format_seconds_to_hms(elapsed_time_sec)

    params = {
        "activity_id": activity_id,
        "name": activity_json.get("name"),
        "distance": distance_meters,
        "moving_time": moving_time_sec,
        "elapsed_time": elapsed_time_sec,
        "elevation": elevation_meters,
        "type": activity_json.get("type"),
        "avg_speed": avg_speed_mps,
        "max_speed": max_speed_mps,
        "suffer_score": activity_json.get("suffer_score"),
        "average_heartrate": activity_json.get("average_heartrate"),
        "max_heartrate": activity_json.get("max_heartrate"),
        "calories": activity_json.get("calories"),
        "conv_distance": conv_distance_miles,
        "conv_elevation_feet": conv_elevation_feet,
        "conv_avg_speed": conv_avg_speed,
        "conv_max_speed": conv_max_speed,
        "conv_moving_time": conv_moving_time,
        "conv_elapsed_time": conv_elapsed_time,
        "hr_zone_1": hr_zone_pcts[0],
        "hr_zone_2": hr_zone_pcts[1],
        "hr_zone_3": hr_zone_pcts[2],
        "hr_zone_4": hr_zone_pcts[3],
        "hr_zone_5": hr_zone_pcts[4],
    }

    session.execute(
        text("""
            UPDATE activities SET
                name = :name,
                distance = :distance,
                moving_time = :moving_time,
                elapsed_time = :elapsed_time,
                total_elevation_gain = :elevation,
                type = :type,
                average_speed = :avg_speed,
                max_speed = :max_speed,
                suffer_score = :suffer_score,
                average_heartrate = :average_heartrate,
                max_heartrate = :max_heartrate,
                calories = :calories,
                conv_distance = :conv_distance,
                conv_elevation_feet = :conv_elevation_feet,
                conv_avg_speed = :conv_avg_speed,
                conv_max_speed = :conv_max_speed,
                conv_moving_time = :conv_moving_time,
                conv_elapsed_time = :conv_elapsed_time,
                hr_zone_1 = :hr_zone_1,
                hr_zone_2 = :hr_zone_2,
                hr_zone_3 = :hr_zone_3,
                hr_zone_4 = :hr_zone_4,
                hr_zone_5 = :hr_zone_5
            WHERE activity_id = :activity_id
        """),
        params
    )
    session.commit()

def extract_hr_zone_percentages(zones_data):
    try:
        return [zone["score"] for zone in zones_data.get("heart_rate", {}).get("custom_zones", [])]
    except Exception:
        return [0.0] * 5

def extract_splits(activity_json, activity_id):
    splits = []
    for lap in activity_json.get("splits_metric", []):
        splits.append({
            "activity_id": activity_id,
            "lap_index": lap.get("lap_index"),
            "distance": lap.get("distance"),
            "elapsed_time": lap.get("elapsed_time"),
            "moving_time": lap.get("moving_time"),
            "average_speed": lap.get("average_speed"),
            "max_speed": lap.get("max_speed"),
            "start_index": lap.get("start_index"),
            "end_index": lap.get("end_index"),
            "split": lap.get("split"),
            "average_heartrate": lap.get("average_heartrate"),
            "pace_zone": lap.get("pace_zone")
        })
    return splits

class ActivityIngestionService:
    def __init__(self, session, athlete_id):
        self.session = session
        self.athlete_id = athlete_id
        self.access_token = get_valid_token(session, athlete_id)
        self.client = StravaClient(self.access_token)

    def ingest_recent(self, lookback_days=DEFAULT_LOOKBACK_DAYS, max_activities=None):
        after = int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())
        activities = self.client.get_activities(after=after, per_page=DEFAULT_PER_PAGE, max_items=max_activities)
        return upsert_activities(self.session, self.athlete_id, activities)

    def ingest_full_history(self, lookback_days=365, max_activities=None):
        return self.ingest_recent(lookback_days, max_activities)

    def ingest_between(self, start_date, end_date, max_activities=None):
        after = int(start_date.timestamp())
        before = int(end_date.timestamp())
        activities = self.client.get_activities(after=after, before=before, per_page=DEFAULT_PER_PAGE, max_items=max_activities)
        return upsert_activities(self.session, self.athlete_id, activities)

def run_enrichment_batch(session, athlete_id, batch_size=DEFAULT_BATCH_SIZE):
    activity_ids = get_activities_to_enrich(session, athlete_id, batch_size)
    for aid in activity_ids:
        enrich_one_activity_with_refresh(session, athlete_id, aid)
