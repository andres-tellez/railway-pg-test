# src/services/enrichment_sync.py

import time
import logging
import requests
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from src.services.token_refresh import ensure_fresh_access_token

log = logging.getLogger("enrichment_sync")
log.setLevel(logging.INFO)

STRAVA_URL = "https://www.strava.com/api/v3/activities/{activity_id}?include_all_efforts=true"
STRAVA_ZONE_URL = "https://www.strava.com/api/v3/activities/{activity_id}/zones"

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
        url = STRAVA_URL.format(activity_id=activity_id)
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            activity_json = resp.json()

            # HR zone enrichment with fallback patch
            hr_zone_pcts = fetch_hr_zone_percentages(activity_id, access_token)
            if not hr_zone_pcts:
                hr_zone_pcts = [0.0, 0.0, 0.0, 0.0, 0.0]

            update_activity_enrichment(session, activity_id, activity_json, hr_zone_pcts)
            log.info(f"✅ Enriched activity {activity_id}")
            return True

        elif resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", DEFAULT_SLEEP))
            log.warning(f"⚠️ 429 Rate Limited. Retry-After: {retry_after}s")
            time.sleep(retry_after)
            return False

        else:
            log.error(f"❌ Failed to enrich {activity_id} — HTTP {resp.status_code}")
            return True  # skip this activity

    except Exception as e:
        log.error(f"🔥 Exception while enriching {activity_id}: {e}")
        return True

def update_activity_enrichment(session, activity_id, activity_json, hr_zone_pcts):
    # Raw values
    distance_meters = activity_json.get("distance")
    elevation_meters = activity_json.get("total_elevation_gain")
    avg_speed_mps = activity_json.get("average_speed")
    max_speed_mps = activity_json.get("max_speed")
    moving_time_sec = activity_json.get("moving_time")
    elapsed_time_sec = activity_json.get("elapsed_time")

    # Converted values
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

def fetch_hr_zone_percentages(activity_id, access_token):
    url = STRAVA_ZONE_URL.format(activity_id=activity_id)
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers, timeout=10)

    if resp.status_code != 200:
        log.warning(f"HR zones not available for activity {activity_id}")
        return None

    zones_data = resp.json()

    for zone_group in zones_data:
        if zone_group.get("type") == "heartrate":
            hr_zones = zone_group.get("zones", [])
            total_time = sum(z.get("time", 0) for z in hr_zones)
            if total_time == 0:
                return None

            zone_pcts = [
                round((z.get("time", 0) / total_time) * 100, 1)
                for z in hr_zones
            ]
            while len(zone_pcts) < 5:
                zone_pcts.append(0.0)
            return zone_pcts
    return None

def run_enrichment_batch(session, athlete_id, batch_size=DEFAULT_BATCH_SIZE):
    try:
        access_token = ensure_fresh_access_token(session, athlete_id)
        activities = get_activities_to_enrich(session, athlete_id, batch_size)

        log.info(f"🔀 Enriching {len(activities)} activities for athlete {athlete_id}")

        for activity_id in activities:
            retries = 0
            while retries < DEFAULT_RETRY_LIMIT:
                success = enrich_one_activity(session, athlete_id, access_token, activity_id)
                if success:
                    break
                retries += 1
                time.sleep(DEFAULT_SLEEP * (DEFAULT_RETRY_BACKOFF ** retries))

        return len(activities)

    except SQLAlchemyError as db_err:
        log.error(f"DB error during enrichment: {db_err}")
        session.rollback()
        return 0

    except Exception as e:
        log.error(f"Unexpected enrichment failure: {e}")
        return 0


def fetch_hr_zone_percentages(activity_id, access_token):
    url = STRAVA_ZONE_URL.format(activity_id=activity_id)
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers, timeout=10)

    if resp.status_code != 200:
        log.warning(f"HR zones not available for activity {activity_id}")
        return None

    zones_data = resp.json()

    for zone_group in zones_data:
        if zone_group.get("type") == "heartrate":
            hr_zones = zone_group.get("distribution_buckets", [])
            
            # Correctly sum times, safely handling nulls
            times = [z.get("time") or 0.0 for z in hr_zones]
            total_time = sum(times)
            
            print(f"✅ total_time raw sum: {total_time}")  # Debug print

            if total_time == 0:
                log.warning(f"No HR data for activity {activity_id}")
                return None

            zone_pcts = [
                round(((z.get("time") or 0.0) / total_time) * 100, 1)
                for z in hr_zones
            ]

            # Only keep first 5 zones (Strava sometimes returns extra buckets)
            zone_pcts = zone_pcts[:5]
            while len(zone_pcts) < 5:
                zone_pcts.append(0.0)

            print(f"✅ zone_pcts computed: {zone_pcts}")  # Debug print

            return zone_pcts

    return None
