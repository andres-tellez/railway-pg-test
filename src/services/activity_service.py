"""
Activity service for ingestion and enrichment logic.
"""

import time
import json
import logging
import os
from datetime import datetime, timedelta
from sqlalchemy import text

from src.services.token_service import get_valid_token
from src.db.dao.split_dao import upsert_splits
from src.db.dao.activity_dao import ActivityDAO
from src.services.strava_access_service import StravaClient
from src.utils.logger import get_logger
from src.utils.conversions import convert_metrics
from src.db.models.activities import Activity

log = get_logger(__name__)
log.setLevel(logging.INFO)

def log_strava_payload(activity_id, activity_json, zones_data, streams):
    """
    Write debug payload to file.
    """
    try:
        os.makedirs("debug_dumps", exist_ok=True)
        with open(
            f"debug_dumps/strava_debug_{activity_id}.json",
            "w",
            encoding="utf-8"
        ) as f:
            json.dump({
                "activity": activity_json,
                "zones": zones_data,
                "streams": streams
            }, f, indent=2)
    except Exception as e:  # pylint: disable=broad-exception-caught
        log.warning("⚠️ Could not write debug payload for %s: %s", activity_id, e)

def get_activities_to_enrich(session, athlete_id, limit):
    """
    Get recent unenriched activities.
    """
    result = session.execute(
        text("""
            SELECT activity_id FROM activities
            WHERE athlete_id = :athlete_id AND type = 'Run'
            ORDER BY start_date DESC
            LIMIT :limit
        """),
        {"athlete_id": athlete_id, "limit": limit}
    )
    return [row.activity_id for row in result.fetchall()]

def enrich_one_activity(session, access_token, activity_id):
    """
    Enrich a single activity with streams, splits, zones.
    """
    try:
        client = StravaClient(access_token)
        retries = 3
        required_fields = ["distance", "moving_time", "average_speed", "name"]
        soft_fields = ["average_heartrate", "suffer_score", "max_speed", "calories"]

        for attempt in range(retries):
            activity_json = client.get_activity(activity_id)
            zones_data = client.get_hr_zones(activity_id)
            streams = client.get_streams(
                activity_id,
                keys=["distance", "time", "velocity_smooth", "heartrate"]
            )

            if all(activity_json.get(field) for field in required_fields):
                break

            log.warning(
                "⚠️ Missing required fields for activity %s, retry %d/%d...",
                activity_id, attempt + 1, retries
            )
            time.sleep(1)
        else:
            raise ValueError(
                f"❌ Critical data missing after retries for activity {activity_id}: "
                f"{[(field, activity_json.get(field)) for field in required_fields]}"
            )

        log_strava_payload(activity_id, activity_json, zones_data, streams)

        missing_soft = [f for f in soft_fields if activity_json.get(f) is None]
        if missing_soft:
            log.warning(
                "⚠️ Partial enrichment for activity %s — missing: %s",
                activity_id, missing_soft
            )

        log.info(
            "➡️ Enriching activity %s — %s",
            activity_id, activity_json.get("name")
        )

        hr_zone_pcts = extract_hr_zone_percentages(zones_data) or [0.0] * 5
        update_activity_enrichment(session, activity_id, activity_json, hr_zone_pcts)

        splits = build_mile_splits(activity_id, streams)
        if splits:
            upsert_splits(session, splits)
            log.info("✅ Synced %d splits for activity %s", len(splits), activity_id)

        return True
    except Exception as e:  # pylint: disable=broad-exception-caught
        log.error("🔥 Exception while enriching %s: %s", activity_id, e)
        raise

def enrich_one_activity_with_refresh(session, athlete_id, activity_id, max_retries=2):
    """
    Attempt enrichment with token refresh and retries.
    """
    for attempt in range(1, max_retries + 1):
        try:
            access_token = get_valid_token(session, athlete_id)
            enrich_one_activity(session, access_token, activity_id)
            session.expire_all()

            enriched = session.query(Activity).filter(
                Activity.activity_id == activity_id,
                Activity.average_speed.isnot(None),
                Activity.suffer_score.isnot(None),
                Activity.average_heartrate.isnot(None),
                Activity.max_speed.isnot(None),
                Activity.calories.isnot(None)
            ).first()

            if enriched:
                log.info(
                    "✅ Enrichment succeeded on attempt %d for activity %s",
                    attempt, activity_id
                )
                return True

            log.warning(
                "⚠️ Enrichment fields missing on attempt %d for %s. Retrying in 5s...",
                attempt, activity_id
            )
            time.sleep(1)

        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(
                "🔥 Enrichment error on attempt %d for %s: %s",
                attempt, activity_id, e
            )
            time.sleep(1)

    log.error("❌ All retries failed — Activity %s has incomplete enrichment.", activity_id)
    raise RuntimeError(f"Enrichment failed for activity {activity_id}")


def update_activity_enrichment(session, activity_id, activity_json, hr_zone_pcts):
    """
    Update enriched fields on activity.
    """
    conv = convert_metrics({
        "distance": activity_json.get("distance"),
        "elevation": activity_json.get("total_elevation_gain"),
        "average_speed": activity_json.get("average_speed"),
        "max_speed": activity_json.get("max_speed"),
        "moving_time": activity_json.get("moving_time"),
        "elapsed_time": activity_json.get("elapsed_time")
    }, ["distance", "elevation", "average_speed", "max_speed", "moving_time", "elapsed_time"])

    for key in ["average_heartrate", "max_speed", "suffer_score", "calories"]:
        if activity_json.get(key) is None:
            log.warning("⚠️ %s missing from activity %s", key, activity_id)

    params = {
        "activity_id": activity_id,
        "name": activity_json.get("name"),
        "distance": activity_json.get("distance"),
        "moving_time": activity_json.get("moving_time"),
        "elapsed_time": activity_json.get("elapsed_time"),
        "elevation": activity_json.get("total_elevation_gain"),
        "type": activity_json.get("type"),
        "avg_speed": activity_json.get("average_speed"),
        "max_speed": activity_json.get("max_speed"),
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
    """
    Compute HR zone percentages.
    """
    try:
        for zone_group in zones_data:
            if zone_group.get("type") == "heartrate":
                buckets = zone_group.get("distribution_buckets", [])
                times = [b.get("time", 0.0) for b in buckets[:5]]
                total_time = sum(times)
                if total_time > 0:
                    return [round((t / total_time) * 100, 2) for t in times]
    except Exception as e:  # pylint: disable=broad-exception-caught
        log.warning("⚠️ HR zone extraction failed: %s", e)
    return [0.0] * 5

def build_mile_splits(activity_id, streams):
    """
    Build mile splits from stream data.
    """
    distances = streams.get("distance", [])
    times = streams.get("time", [])
    paces = streams.get("velocity_smooth", [])
    hrs = streams.get("heartrate", [])

    splits = []
    mile_threshold = 1609.344
    mile_index = 1
    start_index = 0
    speed_threshold = 0.5

    for i, d in enumerate(distances):
        if float(d) < mile_index * mile_threshold - 1e-6:
            continue

        segment_distance = float(d) - float(distances[start_index])
        elapsed_time = float(times[i]) - float(times[start_index])
        moving_time = sum(
            float(times[j]) - float(times[j - 1])
            for j in range(start_index + 1, i + 1)
            if j < len(paces) and float(paces[j]) > speed_threshold
        )

        avg_speed = sum(paces[start_index:i + 1]) / (i + 1 - start_index) if paces else 0
        avg_hr = sum(hrs[start_index:i + 1]) / (i + 1 - start_index) if hrs else None

        segment_distance = round(segment_distance, 2)
        avg_speed = round(avg_speed, 2)
        max_speed_val = round(max(paces[start_index:i + 1]), 2) if paces else None
        avg_hr = round(avg_hr, 2) if avg_hr else None

        conv_data = convert_metrics({
            "distance": segment_distance,
            "average_speed": avg_speed,
            "moving_time": moving_time,
            "elapsed_time": elapsed_time
        }, ["distance", "average_speed", "moving_time", "elapsed_time"])

        splits.append({
            "activity_id": activity_id,
            "lap_index": mile_index,
            "distance": segment_distance,
            "elapsed_time": elapsed_time,
            "moving_time": moving_time,
            "average_speed": avg_speed,
            "max_speed": max_speed_val,
            "start_index": start_index,
            "end_index": i,
            "split": mile_index,
            "average_heartrate": avg_hr,
            "pace_zone": None,
            **conv_data
        })

        start_index = i + 1
        mile_index += 1

    return splits

class ActivityIngestionService:
    """
    Service to ingest activities from Strava.
    """
    def __init__(self, session, athlete_id):
        self.session = session
        self.athlete_id = athlete_id
        self._refresh_client()

    def _refresh_client(self):
        access_token = get_valid_token(self.session, self.athlete_id)
        self.client = StravaClient(access_token)

    def ingest_recent(self, lookback_days, max_activities=None, per_page=200):
        """
        Ingest recent activities within lookback_days.
        """
        self._refresh_client()
        after = int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())
        activities = self.client.get_activities(after=after, per_page=per_page, limit=max_activities)
        activities = [a for a in activities if a.get("type") == "Run"]
        return ActivityDAO.upsert_activities(self.session, self.athlete_id, activities)

    def ingest_full_history(self, lookback_days=None, max_activities=None, per_page=200, dry_run=False):
        """
        Ingest full history with optional filters.
        """
        after = int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp()) if lookback_days else None
        all_activities = self.client.get_activities(after=after, per_page=per_page, limit=max_activities)
        all_activities = [a for a in all_activities if a.get("type") == "Run"]

        if dry_run:
            return all_activities

        if not all_activities:
            return 0

        ActivityDAO.upsert_activities(self.session, self.athlete_id, all_activities)
        return len(all_activities)

    def ingest_between(self, start_date, end_date, max_activities=None, per_page=200):
        """
        Ingest activities between date range.
        """
        self._refresh_client()
        after = int(start_date.timestamp())
        before = int(end_date.timestamp())
        activities = self.client.get_activities(after=after, before=before, per_page=per_page, limit=max_activities)
        activities = [a for a in activities if a.get("type") == "Run"]
        return ActivityDAO.upsert_activities(self.session, self.athlete_id, activities)

def run_enrichment_batch(session, athlete_id, batch_size=10):
    """
    Batch enrichment job for activities.
    """
    activity_ids = get_activities_to_enrich(session, athlete_id, batch_size)
    for aid in activity_ids:
        enrich_one_activity_with_refresh(session, athlete_id, aid)
        time.sleep(1)
