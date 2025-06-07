import time
import logging
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from src.services.token_service import get_valid_token  # ✅ Use new token service
from src.db.dao.split_dao import upsert_splits
from src.services.strava_client import StravaClient

log = logging.getLogger("enrichment_sync")
log.setLevel(logging.INFO)

DEFAULT_BATCH_SIZE = 20
DEFAULT_RETRY_LIMIT = 5
DEFAULT_SLEEP = 5
DEFAULT_RETRY_BACKOFF = 2

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
    if hours > 0:
        return f"{hours}:{minutes:02}:{sec:02}"
    else:
        return f"{minutes}:{sec:02}"

# ------------------------------------------------

def get_activities_to_enrich(session, athlete_id, limit):
    query = text("""
        SELECT activity_id FROM activities
        WHERE athlete_id = :athlete_id
        ORDER BY start_date DESC
        LIMIT :limit
    """)
    result = session.execute(query, {"athlete_id": athlete_id, "limit": limit})
    return [row.activity_id for row in result.fetchall()]

def enrich_one_activity(session, athlete_id, access_token, activity_id):
    try:
        client = StravaClient(session, athlete_id)

        # Fully centralized calls:
        activity_json = client.get_activity(activity_id)
        zones_data = client.get_hr_zones(activity_id)

        hr_zone_pcts = extract_hr_zone_percentages(zones_data)
        if not hr_zone_pcts:
            hr_zone_pcts = [0.0, 0.0, 0.0, 0.0, 0.0]

        update_activity_enrichment(session, activity_id, activity_json, hr_zone_pcts)

        splits = extract_splits(activity_json)
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
        access_token = get_valid_token(session, athlete_id)  # ✅ Main fix here
        return enrich_one_activity(session, athlete_id, access_token, activity_id)
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
        "hr_zone_1_pct": hr_zone_pcts[0],
        "hr_zone_2_pct": hr_zone_pcts[1],
        "hr_zone_3_pct": hr_zone_pcts[2],
        "hr_zone_4_pct": hr_zone_pcts[3],
        "hr_zone_5_pct": hr_zone_pcts[4],
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
            hr_zone_1_pct = :hr_zone_1_pct,
            hr_zone_2_pct = :hr_zone_2_pct,
            hr_zone_3_pct = :hr_zone_3_pct,
            hr_zone_4_pct = :hr_zone_4_pct,
            hr_zone_5_pct = :hr_zone_5_pct
        WHERE activity_id = :activity_id
        """),
        params
    )
    session.commit()

def extract_hr_zone_percentages(zones_data):
    for zone_group in zones_data:
        if zone_group.get("type") == "heartrate":
            hr_zones = zone_group.get("distribution_buckets", [])
            times = [z.get("time") or 0.0 for z in hr_zones]
            total_time = sum(times)

            if total_time == 0:
                log.warning("No HR data available.")
                return None

            zone_pcts = [
                round(((z.get("time") or 0.0) / total_time) * 100, 1)
                for z in hr_zones
            ]

            zone_pcts = zone_pcts[:5]
            while len(zone_pcts) < 5:
                zone_pcts.append(0.0)

            return zone_pcts

    return None

def extract_splits(activity_json):
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

def run_enrichment_batch(session, athlete_id, batch_size=DEFAULT_BATCH_SIZE):
    try:
        activities = get_activities_to_enrich(session, athlete_id, batch_size)
        log.info(f"🔀 Enriching {len(activities)} activities for athlete {athlete_id}")

        for activity_id in activities:
            retries = 0
            while retries < DEFAULT_RETRY_LIMIT:
                success = enrich_one_activity_with_refresh(session, athlete_id, activity_id)
                if success:
                    break
                retries += 1
                log.warning(f"🔁 Retrying activity {activity_id} (attempt {retries})")
                time.sleep(DEFAULT_SLEEP * (DEFAULT_RETRY_BACKOFF ** retries))
        return len(activities)

    except SQLAlchemyError as db_err:
        log.error(f"DB error during enrichment: {db_err}")
        session.rollback()
        return 0

    except Exception as e:
        log.error(f"Unexpected enrichment failure: {e}")
        return 0
