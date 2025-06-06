import time
import logging
from datetime import datetime, timedelta

import src.env_loader


from sqlalchemy import text
from src.db.db_session import get_session
from src.services.strava_client import StravaClient  # ✅ Centralized client only

log = logging.getLogger("backfill_sync")
log.setLevel(logging.INFO)

# --- Conversion helpers ---
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
    return f"{hours}:{minutes:02}:{sec:02}" if hours else f"{minutes}:{sec:02}"

# --- Business logic now fully clean ---
def fetch_hr_zone_percentages(strava: StravaClient, activity_id):
    try:
        zones_data = strava.get_zones(activity_id)
        for zone_group in zones_data:
            if zone_group.get("type") == "heartrate":
                hr_zones = zone_group.get("distribution_buckets", [])
                times = [z.get("time") or 0.0 for z in hr_zones]
                total_time = sum(times)
                if total_time == 0:
                    return None
                zone_pcts = [
                    round(((z.get("time") or 0.0) / total_time) * 100, 1)
                    for z in hr_zones
                ]
                zone_pcts = zone_pcts[:5]
                while len(zone_pcts) < 5:
                    zone_pcts.append(0.0)
                return zone_pcts
    except Exception as e:
        log.warning(f"Failed to fetch HR zones: {e}")
        return None
    return None

def upsert_activity(session, activity_json, hr_zone_pcts):
    params = {
        "activity_id": activity_json["id"],
        "athlete_id": activity_json["athlete"].get("id"),
        "name": activity_json.get("name"),
        "type": activity_json.get("type"),
        "start_date": activity_json.get("start_date"),
        "distance": activity_json.get("distance"),
        "moving_time": activity_json.get("moving_time"),
        "elapsed_time": activity_json.get("elapsed_time"),
        "total_elevation_gain": activity_json.get("total_elevation_gain"),
        "external_id": activity_json.get("external_id"),
        "timezone": activity_json.get("timezone"),
        "average_speed": activity_json.get("average_speed"),
        "max_speed": activity_json.get("max_speed"),
        "suffer_score": activity_json.get("suffer_score"),
        "average_heartrate": activity_json.get("average_heartrate"),
        "max_heartrate": activity_json.get("max_heartrate"),
        "calories": activity_json.get("calories"),
        "conv_distance": meters_to_miles(activity_json.get("distance")),
        "conv_elevation_feet": meters_to_feet(activity_json.get("total_elevation_gain")),
        "conv_avg_speed": mps_to_min_per_mile(activity_json.get("average_speed")),
        "conv_max_speed": mps_to_min_per_mile(activity_json.get("max_speed")),
        "conv_moving_time": format_seconds_to_hms(activity_json.get("moving_time")),
        "conv_elapsed_time": format_seconds_to_hms(activity_json.get("elapsed_time")),
        "hr_zone_1_pct": hr_zone_pcts[0] if hr_zone_pcts else None,
        "hr_zone_2_pct": hr_zone_pcts[1] if hr_zone_pcts else None,
        "hr_zone_3_pct": hr_zone_pcts[2] if hr_zone_pcts else None,
        "hr_zone_4_pct": hr_zone_pcts[3] if hr_zone_pcts else None,
        "hr_zone_5_pct": hr_zone_pcts[4] if hr_zone_pcts else None
    }

    session.execute(text("""
        INSERT INTO activities (
            activity_id, athlete_id, name, type, start_date, distance, moving_time, elapsed_time, 
            total_elevation_gain, external_id, timezone, average_speed, max_speed, suffer_score, 
            average_heartrate, max_heartrate, calories, conv_distance, conv_elevation_feet, 
            conv_avg_speed, conv_max_speed, conv_moving_time, conv_elapsed_time, 
            hr_zone_1_pct, hr_zone_2_pct, hr_zone_3_pct, hr_zone_4_pct, hr_zone_5_pct)
        VALUES (
            :activity_id, :athlete_id, :name, :type, :start_date, :distance, :moving_time, :elapsed_time, 
            :total_elevation_gain, :external_id, :timezone, :average_speed, :max_speed, :suffer_score, 
            :average_heartrate, :max_heartrate, :calories, :conv_distance, :conv_elevation_feet, 
            :conv_avg_speed, :conv_max_speed, :conv_moving_time, :conv_elapsed_time, 
            :hr_zone_1_pct, :hr_zone_2_pct, :hr_zone_3_pct, :hr_zone_4_pct, :hr_zone_5_pct)
        ON CONFLICT (activity_id) DO UPDATE SET
            name = EXCLUDED.name,
            type = EXCLUDED.type,
            distance = EXCLUDED.distance,
            moving_time = EXCLUDED.moving_time,
            elapsed_time = EXCLUDED.elapsed_time,
            total_elevation_gain = EXCLUDED.total_elevation_gain,
            average_speed = EXCLUDED.average_speed,
            max_speed = EXCLUDED.max_speed,
            suffer_score = EXCLUDED.suffer_score,
            average_heartrate = EXCLUDED.average_heartrate,
            max_heartrate = EXCLUDED.max_heartrate,
            calories = EXCLUDED.calories,
            conv_distance = EXCLUDED.conv_distance,
            conv_elevation_feet = EXCLUDED.conv_elevation_feet,
            conv_avg_speed = EXCLUDED.conv_avg_speed,
            conv_max_speed = EXCLUDED.conv_max_speed,
            conv_moving_time = EXCLUDED.conv_moving_time,
            conv_elapsed_time = EXCLUDED.conv_elapsed_time,
            hr_zone_1_pct = EXCLUDED.hr_zone_1_pct,
            hr_zone_2_pct = EXCLUDED.hr_zone_2_pct,
            hr_zone_3_pct = EXCLUDED.hr_zone_3_pct,
            hr_zone_4_pct = EXCLUDED.hr_zone_4_pct,
            hr_zone_5_pct = EXCLUDED.hr_zone_5_pct
    """), params)

def run_backfill(athlete_id, months=6):
    with get_session() as session:
        strava = StravaClient(athlete_id)

        after_date = datetime.utcnow() - timedelta(days=30 * months)
        log.info(f"Fetching data since {after_date.date()}...")

        page = 1
        total_fetched = 0

        while True:
            activities = strava.list_activities(after_date.timestamp(), page=page)
            if not activities:
                break

            log.info(f"Processing page {page} with {len(activities)} activities")
            for activity_json in activities:
                try:
                    hr_zone_pcts = fetch_hr_zone_percentages(strava, activity_json['id'])
                    upsert_activity(session, activity_json, hr_zone_pcts)
                    session.commit()
                    log.info(f"✅ Synced activity {activity_json['id']}")
                    total_fetched += 1
                except Exception as e:
                    log.error(f"❌ Failed to process activity {activity_json['id']}: {e}")
                    session.rollback()

            page += 1
            time.sleep(1)

        log.info(f"✅ Backfill complete — {total_fetched} activities processed.")

if __name__ == "__main__":
    run_backfill(athlete_id=347085, months=6)
