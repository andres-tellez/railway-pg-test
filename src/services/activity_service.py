import time
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.services.token_service import get_valid_token
from src.db.dao.split_dao import upsert_splits
from src.db.dao.activity_dao import ActivityDAO
from src.services.strava_access_service import StravaClient
from src.utils.logger import get_logger
import src.utils.config as config
from src.utils.conversions import convert_metrics, meters_to_miles, mps_to_min_per_mile, format_seconds_to_hms

log = get_logger(__name__)
log.setLevel(logging.INFO)

DEFAULT_BATCH_SIZE = 20
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_PER_PAGE = 200

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
        streams = client.get_streams(activity_id, keys=["distance", "time", "velocity_smooth", "heartrate"])

        log.info(f"📊 streams sample: distances={len(streams.get('distance', []))}, times={len(streams.get('time', []))}")
        log.info(f"➡️ Enriching activity {activity_id}")
        log.info(f"🔍 name: {activity_json.get('name')}")

        hr_zone_pcts = extract_hr_zone_percentages(zones_data) or [0.0] * 5
        update_activity_enrichment(session, activity_id, activity_json, hr_zone_pcts)

        log.info(f"-- streams keys: {list(streams.keys())}")
        splits = build_mile_splits(activity_id, streams)
        log.info(f"--> splits built: {splits}")

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
    conv_fields = ["distance", "elevation", "average_speed", "max_speed", "moving_time", "elapsed_time"]
    conv_data = {
        "distance": activity_json.get("distance"),
        "elevation": activity_json.get("total_elevation_gain"),
        "average_speed": activity_json.get("average_speed"),
        "max_speed": activity_json.get("max_speed"),
        "moving_time": activity_json.get("moving_time"),
        "elapsed_time": activity_json.get("elapsed_time")
    }
    conv = convert_metrics(conv_data, conv_fields)

    params = {
        "activity_id": activity_id,
        "name": activity_json.get("name"),
        "distance": conv_data["distance"],
        "moving_time": conv_data["moving_time"],
        "elapsed_time": conv_data["elapsed_time"],
        "elevation": conv_data["elevation"],
        "type": activity_json.get("type"),
        "avg_speed": conv_data["average_speed"],
        "max_speed": conv_data["max_speed"],
        "suffer_score": activity_json.get("suffer_score"),
        "average_heartrate": activity_json.get("average_heartrate"),
        "max_heartrate": activity_json.get("max_heartrate"),
        "calories": activity_json.get("calories"),
        "hr_zone_1": hr_zone_pcts[0],
        "hr_zone_2": hr_zone_pcts[1],
        "hr_zone_3": hr_zone_pcts[2],
        "hr_zone_4": hr_zone_pcts[3],
        "hr_zone_5": hr_zone_pcts[4],
        **conv
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
        for zone_group in zones_data:
            if zone_group.get("type") == "heartrate":
                buckets = zone_group.get("distribution_buckets", [])
                times = [b.get("time", 0.0) for b in buckets[:5]]
                total_time = sum(times)
                if total_time > 0:
                    return [round((t / total_time) * 100, 2) for t in times]
                else:
                    log.warning("⚠️ Total HR zone time is zero — returning zeros.")
    except Exception as e:
        log.warning(f"⚠️ HR zone extraction failed: {e}")
    return [0.0] * 5

def build_mile_splits(activity_id, streams):
    def get_data(key):
        if isinstance(streams, list):
            for s in streams:
                if s.get("type") == key:
                    return s.get("data", [])
        elif isinstance(streams, dict):
            return streams.get(key, [])
        return []

    distances = get_data("distance")
    times = get_data("time")
    paces = get_data("velocity_smooth")
    hrs = get_data("heartrate")

    log.info(f"-- samples: distances={len(distances)}, times={len(times)}, paces={len(paces)}, hrs={len(hrs)}")

    splits = []
    mile_threshold = 1609.344
    mile_index = 1
    start_index = 0

    try:
        for i, d in enumerate(distances):
            segment_distance = float(d) - float(distances[start_index])

            if i == len(distances) - 1 and segment_distance < (mile_threshold * 0.5):
                break

            if float(d) >= mile_index * mile_threshold or i == len(distances) - 1:
                segment_time = float(times[i]) - float(times[start_index])
                segment_speed = sum(map(float, paces[start_index:i + 1])) / (i + 1 - start_index) if paces else 0
                segment_hr = sum(map(float, hrs[start_index:i + 1])) / (i + 1 - start_index) if hrs else None

                splits.append({
                    "activity_id": activity_id,
                    "lap_index": mile_index,
                    "distance": segment_distance,
                    "elapsed_time": segment_time,
                    "moving_time": segment_time,
                    "average_speed": segment_speed,
                    "max_speed": max(map(float, paces[start_index:i + 1])) if paces else None,
                    "start_index": start_index,
                    "end_index": i,
                    "split": mile_index,
                    "average_heartrate": segment_hr,
                    "pace_zone": None,
                    **convert_metrics({
                        "distance": segment_distance,
                        "average_speed": segment_speed,
                        "moving_time": segment_time,
                        "elapsed_time": segment_time
                    }, ["distance", "average_speed", "moving_time", "elapsed_time"])
                })
                start_index = i + 1
                mile_index += 1
    except Exception as e:
        log.error(f"🔥 Error while building splits: {e}")
        return []

    return splits

class ActivityIngestionService:
    def __init__(self, session, athlete_id):
        self.session = session
        self.athlete_id = athlete_id
        self.access_token = get_valid_token(session, athlete_id)
        self.client = StravaClient(self.access_token)

    def ingest_recent(self, lookback_days=DEFAULT_LOOKBACK_DAYS, max_activities=None):
        after = int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())
        activities = self.client.get_activities(after=after, per_page=DEFAULT_PER_PAGE, limit=max_activities)
        return ActivityDAO.upsert_activities(self.session, self.athlete_id, activities)

    def ingest_full_history(self, lookback_days=365, max_activities=None):
        return self.ingest_recent(lookback_days, max_activities)

    def ingest_between(self, start_date, end_date, max_activities=None):
        after = int(start_date.timestamp())
        before = int(end_date.timestamp())
        activities = self.client.get_activities(after=after, before=before, per_page=DEFAULT_PER_PAGE, limit=max_activities)
        return ActivityDAO.upsert_activities(self.session, self.athlete_id, activities)

def run_enrichment_batch(session, athlete_id, batch_size=DEFAULT_BATCH_SIZE):
    activity_ids = get_activities_to_enrich(session, athlete_id, batch_size)
    for aid in activity_ids:
        enrich_one_activity_with_refresh(session, athlete_id, aid)
